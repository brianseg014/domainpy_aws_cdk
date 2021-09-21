import typing

from aws_cdk import core as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_stepfunctions as stepfunctions
from aws_cdk import aws_stepfunctions_tasks as stepfunctions_tasks
from aws_cdk import aws_sqs as sqs

from domainpy_aws_cdk.scheduler.base import ScheduleEventChannelBase, IIntegrationEventChannelHook


class StepFunctionScheduleEventChannel(ScheduleEventChannelBase):
    class Import(ScheduleEventChannelBase):
        def __init__(self, scope: cdk.Construct, id: str, queue_arn: str, scheduler_arn: str):
            super().__init__(scope, id)

            self.queue = sqs.Queue.from_queue_arn(self, 'queue', queue_arn)
            self.state_machine = stepfunctions.StateMachine.from_state_machine_arn(self, 'scheduler', scheduler_arn)

    @classmethod
    def bring(cls, scope: cdk.Construct, id: str, export_name: str) -> Import:
        queue_arn = cdk.Fn.import_value(f'{export_name}QueueArn')
        scheduler_arn = cdk.Fn.import_value(f'{export_name}SchedulerArn')

        return StepFunctionScheduleEventChannel.Import(scope, id, queue_arn, scheduler_arn)

    def __init__(
        self, 
        scope: cdk.Construct, 
        id: str, 
        *,
        integration_event_hook: IIntegrationEventChannelHook,
        export_name: typing.Optional[str] = None
    ) -> None: 
        super().__init__(scope, id)

        self.queue = sqs.Queue(self, 'queue')

        self.state_machine = stepfunctions.StateMachine(self, 'scheduler',
            definition=(
                stepfunctions.Wait(self, 'wait',
                    time=stepfunctions.WaitTime.timestamp_path("$.publish_at")
                )
                .next(
                    stepfunctions_tasks.SqsSendMessage(self, 'send-to-queue',
                        message_body=stepfunctions.TaskInput.from_json_path_at("$"),
                        queue=self.queue
                    )
                )
            ),
            tracing_enabled=True
        )

        integration_event_hook.bind(self)

        if export_name is not None:
            cdk.CfnOutput(self, 'queue-arn',
                export_name=f'{export_name}QueueArn',
                value=self.queue.queue_arn
            )
            cdk.CfnOutput(self, 'scheduler-arn',
                export_name=f'{export_name}SchedulerArn',
                value=self.state_machine.state_machine_arn
            )
