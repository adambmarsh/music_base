#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
###############################################################################
#
# Copyright (C) 2018 HERE Global B.V. and its affiliate(s).
# All Rights Reserved.
#
# This software and other materials contain proprietary information
# controlled by HERE and are protected by applicable copyright legislation.
# Any use and utilization of this software and other materials and
# disclosure to any third parties is conditional upon having a separate
# agreement with HERE for the access, use, utilization or disclosure of this
# software. In the absence of such agreement, the use of the software is not
# allowed.
#
###############################################################################
import requests


class BaseRequest(object):

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, user):
        self._username = user

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, secret):
        self._password = secret

    @property
    def req_headers(self):
        return self._req_headers

    @req_headers.setter
    def req_headers(self, headers):
        self._req_headers = headers

    def __init__(self, user_name, pass_word, request_headers=None):
        self._username = None
        self._password = None
        self._req_headers = None

        self.username = user_name
        self.password = pass_word
        self.req_headers = {'Content-Type': 'application/json'} if not request_headers else request_headers

    def _submit_request(self, http_method, server_url, request_data, request_headers=None):
        return requests.request(http_method,
                                server_url,
                                data=request_data,
                                auth=(self.username, self.password),
                                headers=self.req_headers if not request_headers else request_headers,
                                verify=True
                                )
