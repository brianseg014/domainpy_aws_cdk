
from aws_cdk import core as cdk

from domainpy_aws_cdk.view.base import IView, ITraceSegmentStoreHook
from domainpy_aws_cdk.view.aws_lambda import LambdaViewBase
from domainpy_aws_cdk.tracestore.aws_dynamodb import DynamoDBTableTraceSegmentStore


class DynamoDBTableTraceSegmentStoreHook(ITraceSegmentStoreHook):

    def __init__(
        self,
        trace_segment_store: DynamoDBTableTraceSegmentStore
    ) -> None:
        self.trace_segment_store = trace_segment_store

    def bind(self, view: IView):
        if isinstance(view, LambdaViewBase):
            self._bind_lambda_view(view)
        else:
            raise cdk.ValidationError('projector-tracesegmentstore incompatible')

    def _bind_lambda_view(self, view: LambdaViewBase):
        function = view.microservice

        function.add_environment('TRACE_SEGMENT_STORE_SERVICE', 'AWS::DynamoDB::Table')
        function.add_environment('TRACE_SEGMENT_STORE_TABLE_NAME', self.trace_segment_store.table.table_name)
        self.trace_segment_store.table.grant_read_write_data(function)
