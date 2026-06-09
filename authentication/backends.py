import jwt
from django.conf import settings
from rest_framework import authentication, exceptions

from .models import User


class JWTAuthentication(authentication.BaseAuthentication):
    # header prefix can be either Token or Bearer
    authentication_header_prefix = "Bearer"

    def authenticate(self, request):
        """
        The `authenticate` method is called on every request regardless of
        whether the endpoint requires authentication.

        `authenticate` has two possible return values:
        1. `None` - e.g:  when the request does not include a token in the
                    headers.
        2. `(user, token)` - when authentication is successful.

        Otherwise raise the `AuthenticationFailed` exception .
        """

        request.user = None

        # `auth_header` should be an array with two elements: 1. the name of
        # the authentication header (in this case, "Token") and 2. the JWT
        # that we should authenticate against.
        auth_header = authentication.get_authorization_header(request).split()
        auth_header_prefix = "bearer"

        if not auth_header:
            return None

        if len(auth_header) == 1 or len(auth_header) > 2:
            # Invalid token header. No credentials provided. or The Token
            # string should not contain spaces.
            return None

        # The JWT library can't handle the `byte` type,
        # So decode `prefix` and `token`. we would get an error
        # if we didn't decode these values.
        prefix = auth_header[0].decode("utf-8")
        token = auth_header[1].decode("utf-8")

        if prefix.lower() != auth_header_prefix:
            # if prefix is not `Bearer`.
            return None

        # Credentials authentication
        return self._authenticate_credentials(request, token)

    def _authenticate_credentials(self, request, token):
        """
        Authenticate the given credentials. If authentication is
        successful, return the user and token. If not, throw an error.
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed(
                "Authentication Failed! Authentication Token is Expired."
            )

        except jwt.InvalidSignatureError:
            raise exceptions.AuthenticationFailed(
                "Authentication Failed! Invalid token signature."
            )
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed(
                "Authentication Failed! Malformed token."
            )
        except Exception as e:
            raise exceptions.AuthenticationFailed(f"Authentication Failed! {str(e)}")

        try:
            user = User.objects.get(pk=payload["id"], is_active=True)

        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed(
                "Authentication Failed! User does not exist."
            )

        if not user.is_active:
            raise exceptions.AuthenticationFailed(
                "Authentication Failed! User no longer exist."
            )

        return user, token
