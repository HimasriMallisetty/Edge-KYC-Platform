import re

from rest_framework.serializers import ValidationError

from .constants import (
    ADDRESS_ERR_MSG,
    USER_NAME_ERR_MSG,
    OTHER_NAME_ERR_MSG,
    PHONE_NUMBER_ERR_MSG,
)


def user_name_validator(name):
    """
    Validate user name (first or last name)

    :param name: name string
    :return: validated data
    """
    pattern = re.compile("^[A-Za-z][A-Z a-z,.'-]*$")

    if pattern.match(name):
        return name

    raise ValidationError(USER_NAME_ERR_MSG.format(name))


def name_validator(name):
    """
    Validate user name (department, job title, kpi name, etc)

    :param name: name string
    :return: validated data
    """
    pattern = re.compile("^[A-Za-z0-9][A-Za-z0-9 ,.'-/\"&`%$():_]*$")

    if pattern.match(name):
        return name

    raise ValidationError(OTHER_NAME_ERR_MSG.format(name))


def phone_validator(phone):
    """
    Validate phone number

    :param phone: phone number string
    :return: validated data
    """
    pattern = re.compile("^[2-9][0-8][0-9][2-9][0-9]{2}[0-9]{4}$")

    if pattern.match(phone):
        return phone

    raise ValidationError(PHONE_NUMBER_ERR_MSG)


def address_validator(address):
    """
    Validate address

    :param address: address string
    :return: validated data
    """
    pattern = re.compile("^\s*\S*\w+\S*(\s\S*\w+\S*)+$")

    if pattern.match(address.strip()):
        return address

    raise ValidationError(ADDRESS_ERR_MSG)
