import os
import tempfile
import shutil
import typing

from aws_cdk import core as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as events_targets
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_sources
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subscriptions
from aws_cdk import aws_stepfunctions as stepfunctions


class EventStore(cdk.Construct):

    def __init__(self, scope: cdk.Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.table = self.create_table()

    def create_table(self):
        return dynamodb.Table(self, 'table',
            partition_key={ 'name': 'stream_id', 'type': dynamodb.AttributeType.STRING },
            sort_key={ 'name': 'number', 'type': dynamodb.AttributeType.NUMBER },
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )


class IdempotentStore(cdk.Construct):

    def __init__(self, scope: cdk.Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.table = self.create_table()

    def create_table(self):
        return dynamodb.Table(self, 'table',
            partition_key={ 'name': 'trace_id', 'type': dynamodb.AttributeType.STRING },
            sort_key={ 'name': 'topic', 'type': dynamodb.AttributeType.STRING },
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )


class Context(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str,
        *,
        entry: str,
        gateway_subscriptions: typing.Sequence[str],
        integration_subscriptions: typing.Dict[str, typing.Sequence[str]],
        event_store: EventStore,
        idempotent_store: IdempotentStore,
        share_prefix: str
    ) -> None:
        super().__init__(scope, construct_id)

        domain_bus = events.EventBus.from_event_bus_name(
            self, 'domain-bus', cdk.Fn.import_value(f'{share_prefix}DomainBusName')
        )
        integration_bus = events.EventBus.from_event_bus_name(
            self, 'integration-bus', cdk.Fn.import_value(f'{share_prefix}IntegrationBusName')
        )
        scheduler = stepfunctions.StateMachine.from_state_machine_arn(
            self, 'scheduler', cdk.Fn.import_value(f'{share_prefix}EventSchedulerArn')
        )

        self.dead_letter_queue = sqs.Queue(self, "dlq")
        self.queue = sqs.Queue(self, "queue",
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=20,
                queue=self.dead_letter_queue
            ),
            visibility_timeout=cdk.Duration.seconds(30),
            receive_message_wait_time=cdk.Duration.seconds(20)
        )

        for message_name in gateway_subscriptions:
            topic = sns.Topic.from_topic_arn(self, message_name, cdk.Fn.import_value(message_name))
            topic.add_subscription(
                sns_subscriptions.SqsSubscription(self.queue, raw_message_delivery=True)
            )

        if len(integration_subscriptions) > 0:
            for context,integration_events_names in integration_subscriptions.items():
                events.Rule(self, f'{context}-integration-rule',
                    event_bus=integration_bus,
                    event_pattern=events.EventPattern(
                        detail_type=integration_events_names,
                        source=[context]
                    ),
                    targets=[
                        events_targets.SqsQueue(
                            self.queue, message=events.RuleTargetInput.from_event_path('$.detail')
                        )
                    ]
                )

        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(entry, tmp, dirs_exist_ok=True)
            shutil.copytree('/Users/brianestrada/Offline/domainpy', os.path.join(tmp, 'domainpy'), dirs_exist_ok=True)

            self.microservice = lambda_.DockerImageFunction(self, 'microservice',
                code=lambda_.DockerImageCode.from_image_asset(
                    directory=tmp
                ),
                environment={
                    'IDEMPOTENT_TABLE_NAME': idempotent_store.table.table_name,
                    'EVENT_STORE_TABLE_NAME': event_store.table.table_name,
                    'DOMAIN_EVENT_BUS_NAME': domain_bus.event_bus_name,
                    'INTEGRATION_EVENT_BUS_NAME': integration_bus.event_bus_name,
                    'EVENT_SCHEDULER_ARN': scheduler.state_machine_arn
                },
                timeout=cdk.Duration.seconds(10),
                tracing=lambda_.Tracing.ACTIVE,
                description='[CONTEXT] Handles commands and integrations and emits domain events'
            )
            self.microservice.add_event_source(lambda_sources.SqsEventSource(self.queue))
            self.microservice.add_event_source(lambda_sources.SqsEventSource(self.dead_letter_queue))

            event_store.table.grant_read_write_data(self.microservice)
            idempotent_store.table.grant_read_write_data(self.microservice)
            domain_bus.grant_put_events_to(self.microservice)
            integration_bus.grant_put_events_to(self.microservice)
            scheduler.grant_start_execution(self.microservice)



class ContextMap(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str,
        *,
        entry: str,
        domain_subscriptions: typing.Dict[str, typing.Sequence[str]],
        integration_subscriptions: typing.Dict[str, typing.Sequence[str]],
        context: Context,
        share_prefix: str
    ) -> None:
        super().__init__(scope, construct_id)

        domain_bus = events.EventBus.from_event_bus_name(
            self, 'domain-bus', cdk.Fn.import_value(f'{share_prefix}DomainBusName')
        )
        integration_bus = events.EventBus.from_event_bus_name(
            self, 'integration-bus', cdk.Fn.import_value(f'{share_prefix}IntegrationBusName')
        )

        self.dead_letter_queue = sqs.Queue(self, "dlq")
        self.queue = sqs.Queue(self, "queue",
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=20,
                queue=self.dead_letter_queue
            ),
            visibility_timeout=cdk.Duration.seconds(30),
            receive_message_wait_time=cdk.Duration.seconds(20)
        )

        if len(domain_subscriptions) > 0:
            for context,domain_events_names in domain_subscriptions.items():
                events.Rule(self, f'{context}-domain-rule',
                    event_bus=domain_bus,
                    event_pattern=events.EventPattern(
                        detail_type=domain_events_names,
                        source=[context]
                    ),
                    targets=[
                        events_targets.SqsQueue(
                            self.queue, message=events.RuleTargetInput.from_event_path('$.detail')
                        )
                    ]
                )

        if len(integration_subscriptions) > 0:
            for context,integration_events_names in integration_subscriptions.items():
                events.Rule(self, f'{context}-integration-rule',
                    event_bus=integration_bus,
                    event_pattern=events.EventPattern(
                        detail_type=integration_events_names,
                        source=[context]
                    ),
                    targets=[
                        events_targets.SqsQueue(
                            self.queue, message=events.RuleTargetInput.from_event_path('$.detail')
                        )
                    ]
                )

        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(entry, tmp, dirs_exist_ok=True)
            shutil.copytree('/Users/brianestrada/Offline/domainpy', os.path.join(tmp, 'domainpy'), dirs_exist_ok=True)

            self.microservice = lambda_.DockerImageFunction(self, "microservice",
                code=lambda_.DockerImageCode.from_image_asset(
                    directory=tmp
                ),
                environment={
                    'CONTEXT_QUEUE_NAME': context.queue.queue_name
                },
                timeout=cdk.Duration.seconds(10),
                tracing=lambda_.Tracing.ACTIVE,
                description='[CONTEXT MAP] Listen for other contexts messages and transforms into known context message'
            )
            self.microservice.add_event_source(lambda_sources.SqsEventSource(self.queue))
            self.microservice.add_event_source(lambda_sources.SqsEventSource(self.dead_letter_queue))

            context.queue.grant_send_messages(self.microservice)
