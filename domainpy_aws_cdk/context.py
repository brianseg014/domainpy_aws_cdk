from __future__ import annotations

import abc
import typing

import constructs
import aws_cdk as cdk
import aws_cdk.aws_ssm as cdk_ssm
import aws_cdk.aws_sqs as cdk_sqs
import aws_cdk.aws_dynamodb as cdk_dynamodb
import aws_cdk.aws_lambda as cdk_lambda
import aws_cdk.aws_lambda_event_sources as cdk_lambda_sources

from .tracestore import TraceStore
from .eventstore import EventStore
from .scheduler import Scheduler
from .constructs.aws_opensearch import Resource


class Context(constructs.Construct):
    def __init__(
        self,
        scope: constructs.Construct,
        id: str,
        *,
        code: cdk_lambda.Code,
        handler: str,
        handler_async: str,
        runtime: cdk_lambda.Runtime,
        memory_size: typing.Optional[typing.Union[int, float]] = None,
        environment: typing.Optional[typing.Mapping[str, str]] = None,
        parameters: typing.Optional[typing.Mapping[str, str]] = None,
        description: typing.Optional[str] = None,
        timeout: typing.Optional[cdk.Duration] = None,
        visibility_timeout: typing.Optional[cdk.Duration] = None,
        receive_message_wait_time: typing.Optional[cdk.Duration] = None,
        batch_size: typing.Optional[int] = None,
        data_destinations: typing.Optional[
            typing.Sequence[DataDestination]
        ] = None,
    ) -> None:
        super().__init__(scope, id)

        self.application = Application(
            self,
            "application",
            code=code,
            handler=handler,
            handler_async=handler_async,
            runtime=runtime,
            memory_size=memory_size,
            environment=environment,
            parameters=parameters,
            description=description,
            timeout=timeout,
            data_destinations=data_destinations,
        )

        self.dlq = cdk_sqs.Queue(
            self,
            "dlq",
            fifo=True,
            content_based_deduplication=False,
        )

        self.queue = cdk_sqs.Queue(
            self,
            "queue",
            dead_letter_queue=cdk_sqs.DeadLetterQueue(
                max_receive_count=20, queue=self.dlq
            ),
            visibility_timeout=visibility_timeout,
            receive_message_wait_time=receive_message_wait_time,
            fifo=True,
            content_based_deduplication=False,
        )

        self.application.function_async.add_event_source(
            cdk_lambda_sources.SqsEventSource(
                self.queue, batch_size=batch_size
            )
        )


class Application(constructs.Construct):
    def __init__(
        self,
        scope: constructs.Construct,
        id: str,
        *,
        code: cdk_lambda.Code,
        handler: str,
        handler_async: str,
        runtime: cdk_lambda.Runtime,
        memory_size: typing.Optional[typing.Union[int, float]] = None,
        environment: typing.Optional[typing.Mapping[str, str]] = None,
        parameters: typing.Optional[typing.Mapping[str, str]] = None,
        description: typing.Optional[str] = None,
        timeout: typing.Optional[cdk.Duration] = None,
        data_destinations: typing.Optional[
            typing.Sequence[DataDestination]
        ] = None,
    ) -> None:
        super().__init__(scope, id)

        self.function = cdk_lambda.Function(
            self,
            "function",
            code=code,
            handler=handler,
            runtime=runtime,
            memory_size=memory_size,
            environment=environment,
            description=description
            or "[Context] Business code for handling messages (sync)",
            timeout=timeout,
            tracing=cdk_lambda.Tracing.ACTIVE,
        )

        self.function_async = cdk_lambda.Function(
            self,
            "function_async",
            code=code,
            handler=handler_async,
            runtime=runtime,
            memory_size=memory_size,
            environment=environment,
            description=description
            or "[Context] Business code for handling messages (async)",
            timeout=timeout,
            tracing=cdk_lambda.Tracing.ACTIVE,
        )

        # Create parameter in AWS SSM Parameter Store
        # and grant read to functions
        if parameters:
            for param, arg in parameters.items():
                parameter = cdk_ssm.StringParameter(
                    self,
                    f"{param}_parameter",
                    parameter_name=param,
                    string_value=arg,
                )
                for fn in self.functions:
                    parameter.grant_read(fn)

        if data_destinations:
            for destination in data_destinations:
                destination.bind(self)

    @property
    def functions(self) -> typing.Iterable[cdk_lambda.Function]:
        yield self.function
        yield self.function_async


class DataDestination(abc.ABC):
    @abc.abstractmethod
    def bind(self, application: Application) -> None:
        pass


class TraceStoreDestination(DataDestination):
    def __init__(self, name: str, tracestore: TraceStore) -> None:
        self.name = name
        self.tracestore = tracestore

    def bind(self, application: Application) -> None:
        for fn in application.functions:
            fn.add_environment(
                f"{self.name}_TRACE_STORE_TABLE_NAME",
                self.tracestore.table.table_name,
            )
            self.tracestore.table.grant_read_write_data(fn)


class EventStoreDestination(DataDestination):
    def __init__(self, name: str, eventstore: EventStore) -> None:
        self.name = name
        self.eventstore = eventstore

    def bind(self, application: Application) -> None:
        for fn in application.functions:
            fn.add_environment(
                f"{self.name}_EVENT_STORE_TABLE_NAME",
                self.eventstore.table.table_name,
            )
            self.eventstore.table.grant_read_write_data(fn)


class SchedulerDestination(DataDestination):
    def __init__(self, name: str, scheduler: Scheduler) -> None:
        self.name = name
        self.scheduler = scheduler

    def bind(self, application: Application) -> None:
        for fn in application.functions:
            fn.add_environment(
                f"{self.name}_SCHEDULER_ARN",
                self.scheduler.state_machine.state_machine_arn,
            )
            self.scheduler.state_machine.grant_start_execution(fn)


class DynamodbTableDestination(DataDestination):
    def __init__(self, name: str, table: cdk_dynamodb.Table) -> None:
        self.name = name
        self.table = table

    def bind(self, application: Application) -> None:
        for fn in application.functions:
            fn.add_environment(
                f"{self.name}_TABLE_NAME", self.table.table_name
            )
            self.table.grant_read_write_data(fn)


class OpenSearchResourceDestination(DataDestination):
    def __init__(self, name: str, resource: Resource) -> None:
        self.name = name
        self.resource = resource

    def bind(self, application: Application) -> None:
        for fn in application.functions:
            fn.add_environment(f"{self.name}_ENDPOINT", self.resource.endpoint)
            fn.add_environment(
                f"{self.name}_RESOURCE_PATH", self.resource.resource_path
            )
            fn.add_environment(f"{self.name}_USERNAME", self.resource.username)
            fn.add_environment(
                f"{self.name}_SECRET", self.resource.secret_name
            )
            self.resource.enhaceddomain.secret.grant_read(fn)
