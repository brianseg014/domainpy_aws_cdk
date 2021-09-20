
from aws_cdk import core as cdk

from domainpy_aws_cdk.projector.base import IProjector, IProjectionHook
from domainpy_aws_cdk.projector.aws_lambda import LambdaProjectorBase
from domainpy_aws_cdk.projection.aws_opensearch import OpenSearchDomainProjection


class OpenSearchDomainProjectionHook(IProjectionHook):

    def __init__(
        self,
        projection: OpenSearchDomainProjection
    ) -> None:
        self.projection = projection

    def bind(self, projector: IProjector):
        if isinstance(projector, LambdaProjectorBase):
            self._bind_lambda_projector(projector)
        else:
            cdk.ValidationError('projector-projection incompatible')

    def _bind_lambda_projector(self, projector: LambdaProjectorBase):
        projection_index = self.projection.index
        projection_domain_credentials = self.projection.open_search_service.domain_credentials
        projection_domain = self.projection.open_search_service.domain
        projector_function = projector.microservice

        projector_function.add_environment('PROJECTION_SERVICE', 'AWS::OpenSearchService::Domain')
        projector_function.add_environment('PROJECTION_URL', f'https://{projection_domain.domain_endpoint}')
        projector_function.add_environment('PROJECTION_INDEX', projection_index)
        projector_function.add_environment('PROJECTION_SECRET_NAME', projection_domain_credentials.secret_name)
        projection_domain_credentials.grant_read(projector_function)
