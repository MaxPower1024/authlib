from authlib.specs.rfc6749 import authenticate_client
from authlib.specs.rfc6749 import (
    OAuth2Error, InvalidRequestError, UnsupportedTokenTypeError
)


class RevocationEndpoint(object):
    """Implementation of revocation endpoint which is described in
    `RFC7009`_.

    :param request: OAuth2Request instance
    :param server: Authorization Server instance

    .. _RFC7009: https://tools.ietf.org/html/rfc7009
    """
    ENDPOINT_NAME = 'revocation'
    SUPPORTED_TOKEN_TYPES = ('access_token', 'refresh_token')
    REVOCATION_ENDPOINT_AUTH_METHODS = ['client_secret_basic']

    def __init__(self, request, server):
        self.request = request
        self.server = server
        self._token = None
        self._client = None

    def __call__(self):
        # make it callable for authorization server
        # ``create_endpoint_response``
        return self.create_revocation_response()

    def authenticate_revocation_endpoint_client(self):
        """Authentication client for revocation endpoint with
        ``REVOCATION_ENDPOINT_AUTH_METHODS``.
        """
        self._client = authenticate_client(
            self.server.query_client,
            request=self.request,
            methods=self.REVOCATION_ENDPOINT_AUTH_METHODS,
        )

    def validate_revocation_request(self):
        """The client constructs the request by including the following
        parameters using the "application/x-www-form-urlencoded" format in
        the HTTP request entity-body:

        token
            REQUIRED.  The token that the client wants to get revoked.

        token_type_hint
            OPTIONAL.  A hint about the type of the token submitted for
            revocation.
        """
        if self.request.body_params:
            params = dict(self.request.body_params)
        else:
            params = dict(self.request.query_params)
        if 'token' not in params:
            raise InvalidRequestError()

        token_type = params.get('token_type_hint')
        if token_type and token_type not in self.SUPPORTED_TOKEN_TYPES:
            raise UnsupportedTokenTypeError()
        token = self.query_token(
            params['token'], token_type, self._client)
        if not token:
            raise InvalidRequestError()
        self._token = token

    def create_revocation_response(self):
        """Validate revocation request and create the response for revocation.
        For example, a client may request the revocation of a refresh token
        with the following request::

            POST /revoke HTTP/1.1
            Host: server.example.com
            Content-Type: application/x-www-form-urlencoded
            Authorization: Basic czZCaGRSa3F0MzpnWDFmQmF0M2JW

            token=45ghiukldjahdnhzdauz&token_type_hint=refresh_token

        :returns: (status_code, body, headers)
        """
        try:
            # The authorization server first validates the client credentials
            self.authenticate_revocation_endpoint_client()
            # then verifies whether the token was issued to the client making
            # the revocation request
            self.validate_revocation_request()
            # the authorization server invalidates the token
            self.revoke_token(self._token)
            try:
                self.server.execute_hook(
                    'after_revoke_token', self._token, self._client)
            except RuntimeError:
                pass
            status = 200
            body = {}
            headers = [
                ('Content-Type', 'application/json'),
                ('Cache-Control', 'no-store'),
                ('Pragma', 'no-cache'),
            ]
        except OAuth2Error as error:
            status = error.status_code
            body = dict(error.get_body())
            headers = error.get_headers()
        return status, body, headers

    def query_token(self, token, token_type_hint, client):
        """Get the token from database/storage by the given token string.
        Developers should implement this method::

            def query_token(self, token, token_type_hint, client):
                if token_type_hint == 'access_token':
                    return Token.query_by_access_token(token, client.client_id)
                if token_type_hint == 'refresh_token':
                    return Token.query_by_refresh_token(token, client.client_id)
                return Token.query_by_access_token(token, client.client_id) or \
                    Token.query_by_refresh_token(token, client.client_id)
        """
        raise NotImplementedError()

    def revoke_token(self, token):
        """Mark token as revoked. Since token MUST be unique, it would be
        dangerous to delete it. Consider this situation:

        1. Jane obtained a token XYZ
        2. Jane revoked (deleted) token XYZ
        3. Bob generated a new token XYZ
        4. Jane can use XYZ to access Bob's resource

        It would be secure to mark a token as revoked::

            def revoke_token(self, token):
                token.revoked = True
                session.add(token)
                session.commit()
        """
        raise NotImplementedError()
