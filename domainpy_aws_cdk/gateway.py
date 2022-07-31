import json
import typing

import constructs
import aws_cdk.aws_iam as cdk_iam
import aws_cdk.aws_apigateway as cdk_apigateway

from .context import Context
from .tracestore import TraceStore
from .constructs.aws_apigateway import LambdaIntegrationNoPermission


class Gateway(constructs.Construct):
    def __init__(
        self,
        scope: constructs.Construct,
        id: str,
        *,
        export_name: typing.Optional[str] = None,
    ) -> None:
        super().__init__(scope, id)

        self.rest_api = cdk_apigateway.RestApi(
            self,
            "rest_api",
            deploy_options=cdk_apigateway.StageOptions(
                stage_name="api", tracing_enabled=True
            ),
        )

        self.parameters_request_validator = cdk_apigateway.RequestValidator(
            self,
            "parameters_request_validator",
            rest_api=self.rest_api,
            request_validator_name="parameters-validator",
            validate_request_parameters=True,
        )

        self.body_request_validator = cdk_apigateway.RequestValidator(
            self,
            "body_request_validator",
            rest_api=self.rest_api,
            request_validator_name="body-validator",
            validate_request_body=True,
        )

        self.roles: typing.Dict[str, cdk_iam.IRole] = {}

    def add_trace_store(
        self, resource_name: str, tracestore: TraceStore
    ) -> None:
        resource = self.rest_api.root.add_resource(resource_name)

        role = cdk_iam.Role(
            self,
            f"Role",
            assumed_by=cdk_iam.ServicePrincipal("apigateway.amazonaws.com"),
        )
        role.add_to_policy(
            cdk_iam.PolicyStatement(
                actions=["dynamodb:Query"],
                resources=[tracestore.table.table_arn],
            )
        )

        resource.add_method(
            "get",
            TraceStoreIntegration(tracestore=tracestore, role=role),
            method_responses=[
                cdk_apigateway.MethodResponse(status_code="200")
            ],
            request_validator=self.parameters_request_validator,
            request_parameters={"method.request.querystring.trace_id": True},
        )

    def add_command(
        self,
        topic: str,
        version: int,
        schema: cdk_apigateway.JsonSchema,
        context: Context,
        *,
        handle_async: bool = False,
    ) -> None:
        resource = self.rest_api.root.add_resource(topic)

        role = self._get_or_create_role_for(context)

        integration: typing.Union[
            ContextCommandAsyncIntegration, ContextCommandIntegration
        ]
        if handle_async:
            integration = ContextCommandAsyncIntegration(
                topic=topic, version=version, context=context, role=role
            )
        else:
            integration = ContextCommandIntegration(
                topic=topic, version=version, context=context, role=role
            )

        resource.add_method(
            "post",
            integration,
            request_models={
                "application/json": cdk_apigateway.Model(
                    self,
                    f"{topic}Model",
                    rest_api=self.rest_api,
                    schema=schema,
                    model_name=topic,
                )
            },
            request_validator=self.body_request_validator,
            method_responses=[
                cdk_apigateway.MethodResponse(status_code="200")
            ],
        )

    def add_query(
        self,
        topic: str,
        version: int,
        parameters: typing.Mapping[str, bool],
        context: Context,
        *,
        handle_async: bool = False,
    ) -> None:
        resource = self.rest_api.root.add_resource(topic)

        role = self._get_or_create_role_for(context)

        integration: typing.Union[
            ContextQueryAsyncIntegration, ContextQueryAsyncIntegration
        ]
        if handle_async:
            integration = ContextQueryAsyncIntegration(
                topic=topic, version=version, context=context, role=role
            )
        else:
            integration = ContextQueryAsyncIntegration(
                topic=topic, version=version, context=context, role=role
            )

        resource.add_method(
            "get",
            integration,
            request_validator=self.parameters_request_validator,
            method_responses=[
                cdk_apigateway.MethodResponse(status_code="200")
            ],
            request_parameters=parameters,
        )

    def _get_or_create_role_for(self, context: Context):
        if context.node.path in self.roles:
            return self.roles[context.node.path]

        role = cdk_iam.Role(
            self,
            "role",
            assumed_by=cdk_iam.ServicePrincipal("apigateway.amazonaws.com"),
        )
        role.add_to_policy(
            cdk_iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[context.application.function.function_arn],
            )
        )
        role.add_to_policy(
            cdk_iam.PolicyStatement(
                actions=["sqs:SendMessage"],
                resources=[context.queue.queue_arn],
            )
        )

        self.roles[context.node.path] = role

        return role


class TraceStoreIntegration(cdk_apigateway.AwsIntegration):
    def __init__(self, *, tracestore: TraceStore, role: cdk_iam.IRole) -> None:
        super().__init__(
            service="dynamodb",
            action="Query",
            options=cdk_apigateway.IntegrationOptions(
                credentials_role=role,
                passthrough_behavior=cdk_apigateway.PassthroughBehavior.NEVER,
                request_templates={
                    "application/json": json.dumps(
                        {
                            "TableName": tracestore.table.table_name,
                            "KeyConditionExpression": "#trace_id = :trace_id",
                            "ExpressionAttributeNames": {
                                "#trace_id": "trace_id"
                            },
                            "ExpressionAttributeValues": {
                                ":trace_id": {
                                    "S": "$method.request.querystring.trace_id"
                                }
                            },
                        }
                    )
                },
                integration_responses=[
                    cdk_apigateway.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": """
                            #set($root = $input.path('$'))
                            {
                                "segments": [
                                    #foreach($segment in $root.Items) {
                                        "segment_id": "$segment.segment_id.S",
                                        "errors": [
                                            #foreach($error in $segment.errors.L)
                                                "$error.S"#if($foreach.hasNext),#end
                                            #end
                                        ],
                                        "fatal": $segment.fatal.BOOL,
                                        "primary": $segment.primary.BOOL
                                    }#if($foreach.hasNext),#end
                                    #end
                                ]
                            }
                            """
                        },
                    )
                ],
            ),
        )


class ContextCommandIntegration(LambdaIntegrationNoPermission):
    def __init__(
        self,
        *,
        topic: str,
        version: int,
        context: Context,
        role: cdk_iam.IRole,
    ) -> None:
        super().__init__(
            context.application.function,
            proxy=False,
            credentials_role=role,
            passthrough_behavior=cdk_apigateway.PassthroughBehavior.NEVER,
            request_templates={
                "application/json": f"""
                #set($trace_id = $input.params().header.get("x-trace-id"))
                #if(!$trace_id)
                    #set($trace_id = $context.requestId)
                #end
                {{
                    "type": "COMMAND",
                    "message": {{
                        "topic": "{topic}",
                        "version": {version},
                        "timestamp": "$context.requestTimeEpoch",
                        "command": "$input.json('$')",
                        "message_id": "$trace_id",
                        "correlation_id": "$trace_id",
                        "trace_id": "$trace_id"
                    }}
                }}
                """
            },
            integration_responses=[
                cdk_apigateway.IntegrationResponse(status_code="200")
            ],
        )


class ContextCommandAsyncIntegration(cdk_apigateway.AwsIntegration):
    def __init__(
        self,
        *,
        topic: str,
        version: int,
        context: Context,
        role: cdk_iam.IRole,
    ) -> None:
        super().__init__(
            service="sqs",
            action="SendMessage",
            options=cdk_apigateway.IntegrationOptions(
                credentials_role=role,
                passthrough_behavior=cdk_apigateway.PassthroughBehavior.NEVER,
                request_templates={
                    "application/json": f"""
                    #set($trace_id = $input.params().header.get("x-trace-id"))
                    #if(!$trace_id)
                        #set($trace_id = $context.requestId)
                    #end
                    {{
                        "QueueUrl": "{context.queue.queue_url}",
                        "MessageBody": {{
                            "type": "COMMAND",
                            "message": {{
                                "topic": "{topic}",
                                "version": "{version}",
                                "timestamp": "$context.requestTimeEpoch",
                                "command": "$input.json('$')",
                                "message_id": "$trace_id",
                                "correlation_id": "$trace_id",
                                "trace_id": "$trace_id"
                            }}
                        }},
                        "MessageDeduplicationId": "$trace_id",
                        "MessageGroupId": "$trace_id"
                    }}
                    """
                },
                integration_responses=[
                    cdk_apigateway.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": """
                            #set($trace_id = $input.params().header.get("x-trace-id"))
                            #if(!$trace_id)
                                #set($trace_id = $context.requestId)
                            #end
                            {
                                "trace_id": "$trace_id"
                            }
                            """
                        },
                    )
                ],
            ),
        )


class ContextQueryIntegration(LambdaIntegrationNoPermission):
    def __init__(
        self,
        *,
        topic: str,
        version: int,
        parameters: typing.Mapping[str, bool],
        context: Context,
        role: cdk_iam.IRole,
    ) -> None:
        super().__init__(
            context.application.function,
            proxy=False,
            credentials_role=role,
            passthrough_behavior=cdk_apigateway.PassthroughBehavior.NEVER,
            request_templates={
                "application/json": f"""
                #set($trace_id = $input.params().header.get("x-trace-id"))
                #if(!$trace_id)
                    #set($trace_id = $context.requestId)
                #end
                {{
                    "type": "QUERY",
                    "message": {{
                        "topic": "{topic}",
                        "version": {version},
                        "timestamp": "$context.requestTimeEpoch",
                        "query": $util.toJson($input.params().querystring),
                        "message_id": "$trace_id",
                        "correlation_id": "$trace_id",
                        "trace_id": "$trace_id"
                    }}
                }}
                """
            },
            integration_responses=[
                cdk_apigateway.IntegrationResponse(status_code="200")
            ],
        )


class ContextQueryAsyncIntegration(cdk_apigateway.AwsIntegration):
    def __init__(
        self,
        *,
        topic: str,
        version: int,
        context: Context,
        role: cdk_iam.IRole,
    ) -> None:
        super().__init__(
            service="sqs",
            action="SendMessage",
            options=cdk_apigateway.IntegrationOptions(
                credentials_role=role,
                passthrough_behavior=cdk_apigateway.PassthroughBehavior.NEVER,
                request_templates={
                    "application/json": f"""
                    #set($trace_id = $input.params().header.get("x-trace-id"))
                    #if(!$trace_id)
                        #set($trace_id = $context.requestId)
                    #end
                    {{
                        "QueueUrl": "{context.queue.queue_url}",
                        "MessageBody": {{
                            "type": "QUERY",
                            "message": {{
                                "topic": "{topic}",
                                "version": {version},
                                "timestamp": "$context.requestTimeEpoch",
                                "query": $util.toJson($input.params().querystring),
                                "message_id": "$trace_id",
                                "correlation_id": "$trace_id",
                                "trace_id": "$trace_id"
                            }}
                        }},
                        "MessageDeduplicationId": "$trace_id",
                        "MessageGroupId": "$trace_id"
                    }}
                    """
                },
                integration_responses=[
                    cdk_apigateway.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": """
                            #set($trace_id = $input.params().header.get("x-trace-id"))
                            #if(!$trace_id)
                                #set($trace_id = $context.requestId)
                            #end
                            {
                                "trace_id": "$trace_id"
                            }
                            """
                        },
                    )
                ],
            ),
        )
