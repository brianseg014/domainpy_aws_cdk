
from aws_cdk import core as cdk

from domainpy_aws_cdk.constructs.scheduler import EventScheduler


class EventSchedulerStack(cdk.Stack):

    def __init__(
        self,
        scope: cdk.Construct,
        construct_id: str,
        *,
        share_prefix: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        EventScheduler(
            self, 'eventscheduler', share_prefix=share_prefix
        )
