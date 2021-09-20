import typing

from aws_cdk import core as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python as lambda_python
from aws_cdk import aws_stepfunctions as stepfunctions
from aws_cdk import aws_stepfunctions_tasks as tasks

from domainpy_aws_cdk.scheduler.base import SchedulerChannelBase, IIntegrationEventChannelHook


class StepFunctionSchedulerChannel(SchedulerChannelBase):
    class Import(SchedulerChannelBase):
        def __init__(self, scope: cdk.Construct, id: str, role_arn: str, scheduler_arn: str):
            super().__init__(scope, id)

            self.role = iam.Role.from_role_arn(self, 'role', role_arn)
            self.state_machine = stepfunctions.StateMachine.from_state_machine_arn(self, 'scheduler', scheduler_arn)

    @classmethod
    def bring(cls, scope: cdk.Construct, id: str, export_name: str) -> Import:
        role_arn = cdk.Fn.import_value(f'{export_name}RoleArn')
        scheduler_arn = cdk.Fn.import_value(f'{export_name}SchedulerArn')

        return StepFunctionSchedulerChannel.Import(scope, id, role_arn, scheduler_arn)

    def __init__(
        self, 
        scope: cdk.Construct, 
        id: str, 
        *, 
        integration_channel_hook: IIntegrationEventChannelHook,
        export_name: typing.Optional[str] = None
    ) -> None: 
        super().__init__(scope, id)
        integration_channel_hook.bind(self)

        self.role = iam.Role(self, 'role',
            assumed_by=iam.ServicePrincipal('apigateway.amazonaws.com')
        )

        self.state_machine = stepfunctions.StateMachine(self, 'scheduler',
            definition=(
                stepfunctions.Wait(self, 'wait',
                    time=stepfunctions.WaitTime.timestamp_path("$.publish_at")
                )
                .next(tasks.LambdaInvoke(self, 'publisher-invoke', lambda_function=integration_channel_hook.function))
            )
        )
        self.state_machine.grant_start_execution(self.role)

        if export_name is not None:
            cdk.CfnOutput(self, 'role-arn',
                export_name=f'{export_name}RoleArn',
                value=self.role.role_arn
            )
            cdk.CfnOutput(self, 'scheduler-arn',
                export_name=f'{export_name}SchedulerArn',
                value=self.state_machine.state_machine_arn
            )
