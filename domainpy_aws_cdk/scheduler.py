import typing

import constructs
import aws_cdk.aws_sqs as cdk_sqs
import aws_cdk.aws_stepfunctions as cdk_stepfunctions
import aws_cdk.aws_stepfunctions_tasks as cdk_stepfunctions_tasks


class Scheduler(constructs.Construct):
    def __init__(
        self,
        scope: constructs.Construct,
        id: str,
        *,
        export_name: typing.Optional[str] = None,
    ) -> None:
        super().__init__(scope, id)

        self.queue = cdk_sqs.Queue(self, "queue")

        self.state_machine = cdk_stepfunctions.StateMachine(
            self,
            "scheduler",
            definition=(
                cdk_stepfunctions.Wait(
                    self,
                    "wait",
                    time=cdk_stepfunctions.WaitTime.timestamp_path(
                        "$.publish_at"
                    ),
                ).next(
                    cdk_stepfunctions_tasks.SqsSendMessage(
                        self,
                        "send_to_queue",
                        message_body=cdk_stepfunctions.TaskInput.from_json_path_at(
                            "$"
                        ),
                        queue=self.queue,
                    )
                )
            ),
            tracing_enabled=True,
        )
