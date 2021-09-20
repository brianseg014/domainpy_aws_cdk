
from aws_cdk import core as cdk

from domainpy_aws_cdk.projector.base import IProjector, IProjectionHook
from domainpy_aws_cdk.projector.aws_lambda import LambdaProjectorBase
from domainpy_aws_cdk.projection.aws_dynamodb import DynamoDBTableProjection


class DynamoDBTableProjectionHook(IProjectionHook):

    def __init__(
        self,
        projection: DynamoDBTableProjection
    ) -> None:
        self.projection = projection

    def bind(self, projector: IProjector):
        if isinstance(projector, LambdaProjectorBase):
            self._bind_lambda_projector(projector)
        else:
            projector_type = projector.__class__.__name__
            projection_type = self.projection.__class__.__name__
            raise Exception(f'projector-projection incompatible: {projector_type}-{projection_type}')

    def _bind_lambda_projector(self, projector: LambdaProjectorBase):
        projection_table = self.projection.table
        projector_function = projector.microservice

        projector_function.add_environment('PROJECTION_SERVICE', 'AWS::DynamoDB::Table')
        projector_function.add_environment('PROJECTION_TABLE_NAME', projection_table.table_name)
        projection_table.grant_read_write_data(projector_function)
