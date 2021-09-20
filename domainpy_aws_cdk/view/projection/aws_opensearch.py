
from aws_cdk import core as cdk

from domainpy_aws_cdk.view.base import IView, IProjectionHook
from domainpy_aws_cdk.view.aws_lambda import LambdaViewBase
from domainpy_aws_cdk.projection.aws_opensearch import OpenSearchDomainProjection


class OpenSearchDomainProjectionHook(IProjectionHook):

    def __init__(
        self,
        projection: OpenSearchDomainProjection
    ) -> None:
        self.projection = projection

    def bind(self, view: IView):
        if isinstance(view, LambdaViewBase):
            self._bind_lambda_view(view)
        else:
            cdk.ValidationError('view-projection incompatible')

    def _bind_lambda_view(self, view: LambdaViewBase):
        projection_index = self.projection.index
        projection_domain_credentials = self.projection.open_search_service.domain_credentials
        projection_domain = self.projection.open_search_service.domain
        projector_function = view.microservice

        projector_function.add_environment('PROJECTION_SERVICE', 'AWS::OpenSearchService::Domain')
        projector_function.add_environment('PROJECTION_URL', f'https://{projection_domain.domain_endpoint}')
        projector_function.add_environment('PROJECTION_INDEX', projection_index)
        projector_function.add_environment('PROJECTION_SECRET_NAME', projection_domain_credentials.secret_name)
        projection_domain_credentials.grant_read(projector_function)
