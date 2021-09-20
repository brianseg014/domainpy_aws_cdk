
from aws_cdk import core as cdk

from domainpy_aws_cdk.view.base import IView, IProjectionHook
from domainpy_aws_cdk.view.aws_lambda import LambdaViewBase
from domainpy_aws_cdk.projection.aws_dynamodb import DynamoDBTableProjection


class DynamoDBTableProjectionHook(IProjectionHook):

    def __init__(
        self,
        projection: DynamoDBTableProjection
    ) -> None:
        self.projection = projection

    def bind(self, view: IView):
        if isinstance(view, LambdaViewBase):
            self._bind_lambda_view(view)
        else:
            cdk.ValidationError('projector-projection incompatible')

    def _bind_lambda_view(self, view: LambdaViewBase):
        projection_table = self.projection.table
        view_function = view.microservice

        view_function.add_environment('PROJECTION_SERVICE', 'AWS::DynamoDB::Table')
        view_function.add_environment('PROJECTION_TABLE_NAME', projection_table.table_name)
        projection_table.grant_read_write_data(view_function)
