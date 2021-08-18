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


class EventStore(cdk.Construct):

    def __init__(self, scope: cdk.Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.table = dynamodb.Table(self, 'table',
            partition_key={ 'name': 'stream_id', 'type': dynamodb.AttributeType.STRING },
            sort_key={ 'name': 'number', 'type': dynamodb.AttributeType.NUMBER },
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

    @property
    def table_name(self) -> str:
        return self.table.table_name

    def grant_read_write_data(self, gratee: iam.IGrantable) -> iam.Grant:
        return self.table.grant_read_write_data(gratee)


class IdempotentStore(cdk.Construct):

    def __init__(self, scope: cdk.Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.table = dynamodb.Table(self, 'table',
            partition_key={ 'name': 'trace_id', 'type': dynamodb.AttributeType.STRING },
            sort_key={ 'name': 'topic', 'type': dynamodb.AttributeType.STRING },
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

    @property
    def table_name(self):
        return self.table.table_name

    def grant_read_write_data(self, gratee: iam.IGrantable) -> iam.Grant:
        return self.table.grant_read_write_data(gratee)
    


class Context(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str,
        *,
        entry: str,
        gateway_subscriptions: typing.Sequence[str],
        integration_subscriptions: typing.Sequence[str],
        integration_sources: typing.Sequence[str],
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

        dlq = sqs.Queue(self, "dlq")
        queue = sqs.Queue(self, "queue",
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=20,
                queue=dlq
            ),
            visibility_timeout=cdk.Duration.seconds(30),
            receive_message_wait_time=cdk.Duration.seconds(20)
        )

        for message_name in gateway_subscriptions:
            topic = sns.Topic.from_topic_arn(self, message_name, cdk.Fn.import_value(message_name))
            topic.add_subscription(
                sns_subscriptions.SqsSubscription(queue, raw_message_delivery=True)
            )

        if len(integration_subscriptions) > 0:
            events.Rule(self, 'integration-rule',
                event_bus=integration_bus,
                event_pattern=events.EventPattern(
                    detail_type=integration_subscriptions,
                    source=integration_sources
                ),
                targets=[
                    events_targets.SqsQueue(
                        queue, message=events.RuleTargetInput.from_event_path('$.detail')
                    )
                ]
            )

        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(entry, tmp, dirs_exist_ok=True)
            shutil.copytree('/Users/brianestrada/Offline/domainpy', os.path.join(tmp, 'domainpy'), dirs_exist_ok=True)

            microservice = lambda_.DockerImageFunction(self, 'microservice',
                code=lambda_.DockerImageCode.from_image_asset(
                    directory=tmp
                ),
                environment={
                    'IDEMPOTENT_TABLE_NAME': idempotent_store.table_name,
                    'EVENT_STORE_TABLE_NAME': event_store.table_name,
                    'DOMAIN_EVENT_BUS_NAME': domain_bus.event_bus_name,
                    'INTEGRATION_EVENT_BUS_NAME': integration_bus.event_bus_name,
                },
                timeout=cdk.Duration.seconds(10),
                tracing=lambda_.Tracing.ACTIVE,
                description='[CONTEXT] Handles commands and integrations and emits domain events'
            )
            microservice.add_event_source(lambda_sources.SqsEventSource(queue))
            microservice.add_event_source(lambda_sources.SqsEventSource(dlq))

        event_store.grant_read_write_data(microservice)
        idempotent_store.grant_read_write_data(microservice)
        domain_bus.grant_put_events_to(microservice)
        integration_bus.grant_put_events_to(microservice)

        self.queue = queue
        self.microservice = microservice

    def add_environment(self, key: str, value: str):
        self.microservice.add_environment(key, value)

    @property
    def queue_name(self):
        return self.queue.queue_name


class ContextMap(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str,
        *,
        entry: str,
        domain_subscriptions: typing.Sequence[str],
        domain_sources: typing.Sequence[str],
        integration_subscriptions: typing.Sequence[str],
        integration_sources: typing.Sequence[str],
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

        queue = sqs.Queue(self, "queue",
            content_based_deduplication=True,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=20,
                queue=sqs.Queue(self, "dlq")
            ),
            visibility_timeout=cdk.Duration.seconds(30),
            receive_message_wait_time=cdk.Duration.seconds(20)
        )

        if len(domain_subscriptions) > 0:
            events.Rule(self, 'domain-rule',
                event_bus=domain_bus,
                event_pattern=events.EventPattern(
                    detail_type=domain_subscriptions,
                    source=domain_sources
                ),
                targets=[events_targets.SqsQueue(queue)]
            )

        if len(integration_subscriptions) > 0:
            events.Rule(self, 'integration-rule',
                event_bus=integration_bus,
                event_pattern=events.EventPattern(
                    detail_type=integration_subscriptions,
                    source=integration_sources
                ),
                targets=[events_targets.SqsQueue(queue)]
            )

        microservice = lambda_.DockerImageFunction(self, "microservice",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=entry
            ),
            environment={
                'CONTEXT_QUEUE_NAME': context.queue_name
            },
            timeout=cdk.Duration.seconds(10),
            tracing=lambda_.Tracing.ACTIVE,
            description='[CONTEXT MAP] Listen for other contexts messages and transforms into known context message'
        )
        microservice.add_event_source(lambda_sources.SqsEventSource(queue))

        self.microservice = microservice

    def add_environment(self, key: str, value: str):
        self.microservice.add_environment(key, value)
