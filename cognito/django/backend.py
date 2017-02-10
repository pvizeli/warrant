import abc

from boto3.exceptions import Boto3Error
from django import VERSION as DJANGO_VERSION
from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

from cognito import User as CognitoUser


class Pk(object):

    def value_to_string(self,user):
        return str(user.pk)


class Meta(object):

    def __init__(self,user):
        self.pk = Pk()


class AbstractCognitoUserPoolAuthBackend(ModelBackend):
    create_unknown_user = True

    supports_inactive_user = False

    INACTIVE_USER_STATUS = ['ARCHIVED', 'COMPROMISED', 'UNKNOWN']

    def authenticate(self, username=None, password=None):
        """
        Authenticate a Cognito User.
        """
        cognito_user = CognitoUser(
            settings.COGNITO_USER_POOL_ID,settings.COGNITO_APP_ID,
            username=username, password=password)
        try:
            cognito_user.authenticate()
        except Boto3Error:
            return None
        user_obj = cognito_user.get_user()
        if not self.supports_inactive_user and user_obj.user_status in AbstractCognitoUserPoolAuthBackend.INACTIVE_USER_STATUS:
            return None

        return self._update_or_create_user(user_obj, cognito_user)

    def _update_or_create_user(self, user_obj, cognito_user):
        UserModel = get_user_model()
        if self.create_unknown_user:
            user, created = UserModel.objects.update_or_create(
                username=user_obj.username,
                defaults={
                    'email':user_obj.email,
                    'first_name':user_obj.given_name,
                    'last_name':user_obj.family_name,
                })
        else:
            try:
                user = UserModel.objects.get(username=user_obj.username)
            except UserModel.DoesNotExist:
                user = None
        # Attach tokens to user object
        if user:
            setattr(user, 'access_token', cognito_user.access_token)
            setattr(user, 'id_token', cognito_user.id_token)
            setattr(user, 'refresh_token', cognito_user.refresh_token)
        return user            


if DJANGO_VERSION[1] > 10:
    class CognitoUserPoolAuthBackend(AbstractCognitoUserPoolAuthBackend):
        def authenticate(self, request, username=None, password=None):
            """
            Authenticate a cognito User and store an access, ID and 
            refresh token in the session.

            """
            user = super(CognitoUserPoolAuthBackend, self).authenticate(
                username=username, password=password)
            if user:
                request.session['ACCESS_TOKEN'] = user.access_token
                request.session['ID_TOKEN'] = user.id_token
                request.session['REFRESH_TOKEN'] = user.refresh_token
                request.session.save()
            return user

else:
    class CognitoUserPoolAuthBackend(AbstractCognitoUserPoolAuthBackend):
        def authenticate(self, username=None, password=None):
            """
            Authenticate a cognito User
            """
            return super(CognitoUserPoolAuthBackend, self).authenticate(
                username=username, password=password)

