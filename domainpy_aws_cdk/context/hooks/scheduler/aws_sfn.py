
from aws_cdk import core as cdk

from domainpy_aws_cdk.context.base import IContext, IChannelHook
from domainpy_aws_cdk.context.aws_lambda import LambdaContextBase
from domainpy_aws_cdk.scheduler.aws_sfn import StepFunctionScheduleEventChannel


class StepFunctionSchedulerChannelHook(IChannelHook):

    def __init__(
        self,
        channel_name: str,
        channel: StepFunctionScheduleEventChannel
    ) -> None:
        self.channel_name = channel_name
        self.channel = channel

    def bind(self, context: IContext):
        if isinstance(context, LambdaContextBase):
            self._bind_lambda_context(context)
        else:
            raise cdk.ValidationError('context-scheduler incompatible')

    def _bind_lambda_context(self, context: LambdaContextBase):
        context_function = context.microservice
        channel_state_machine = self.channel.state_machine

        context_function.add_environment(f'{self.channel_name}_SERVICE', 'AWS::StepFunctions::StateMachine')
        context_function.add_environment(f'{self.channel_name}_STATE_MACHINE_ARN', channel_state_machine.state_machine_arn)
        channel_state_machine.grant_start_execution(context_function)
