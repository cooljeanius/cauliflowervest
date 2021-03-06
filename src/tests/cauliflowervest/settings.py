#!/usr/bin/env python
# 
# Copyright 2011 Google Inc. All Rights Reserved.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# #

"""Configurable settings module shared between the client and server."""




# Set SUBDOMAIN to your App Engine application identifier.

# Change DOMAIN from appspot.com to your domain only if using a
# Google Apps domain to host your App Engine application.
# For more details, see: http://code.google.com/appengine/articles/domains.html

SUBDOMAIN = ''
DOMAIN = 'appspot.com'

SERVER_HOSTNAME = '%s.%s' % (SUBDOMAIN, DOMAIN)
SERVER_PORT = 443

FILEVAULT_REQUIRED_PROPERTIES = ['hdd_serial', 'platform_uuid', 'serial']
