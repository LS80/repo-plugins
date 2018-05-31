###############################################################################
#
# MIT License
#
# Copyright (c) 2017 Lee Smith
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################

'''
Module for extracting live channel links from the BT Sport website
'''

from datetime import datetime
import time
from collections import namedtuple

import requests
from bs4 import BeautifulSoup
import pytz


class BTError(EnvironmentError):
    '''Exception for errors related to BT video streams'''
    pass


CATEGORIES_URL = 'http://sport.bt.com/all-videos/videos-01364228997406'
API_URL = 'http://api-search.sport.bt.com/search/sport/select'

_Video = namedtuple('Video', 'title url thumbnail date duration')
_Category = namedtuple('Category', 'title path')


class _Channel(namedtuple('Channel', 'name id epg_index logo')):
    '''Class holding information about a live channel'''
    @property
    def thumbnail(self):
        '''Returns the channel thumbnail URL'''
        return (
            'http://images.atlas.metabroadcast.com/'
            'shaman.metabroadcast.com/bt/channels/{filename}'.format(filename=self.logo)
        )


_EPG = namedtuple('EPG', 'now next')
_Program = namedtuple('Program', 'title synopsis start')


_CHANNELS = [
    _Channel(name='BT Sport 1', id=2020, epg_index=2, logo='BTSPORT_1_201805110826.jpg'),
    _Channel(name='BT Sport 2', id=2021, epg_index=4, logo='BTSPORT_2_201805110826.jpg'),
    _Channel(name='BT Sport 3', id=2030, epg_index=9, logo='BTSPORT_3_201805110828.jpg'),
    _Channel(name='BT Sport//ESPN', id=2022, epg_index=13, logo='BTSPORT_ESPN_201805110829.jpg'),
    _Channel(name='BoxNation', id=2029, epg_index=5, logo='BoxNation_Lozenge_201804201100.jpg')
]


def channels():
    '''Returns the list of channels'''
    return _CHANNELS


def channels_by_id():
    '''Returns a dictionary of channels keyed on the channel id string'''
    return dict((str(channel.id), channel) for channel in _CHANNELS)


def login(user, password):
    '''Returns a session cookie. Returns None if the login failed'''
    response = requests.post(
        'https://signin1.bt.com/siteminderagent/forms/login.fcc',
        data=dict(TARGET='https://home.bt.com/secure/', USER=user, PASSWORD=password)
    )
    return response.cookies.get('SMSESSION')


def sport_login(session):
    '''Returns an AVS cookie'''
    html = requests.get(
        'https://samlfed.bt.com/sportgetfedwebhls',
        cookies=dict(SMSESSION=session)
    ).text
    soup = BeautifulSoup(html, 'html.parser')
    saml_response = soup.find('input', attrs={'name': 'SAMLResponse'})['value']

    response = requests.post(
        'https://be.avs.bt.com/AVS/besc',
        params=dict(action='LoginBT', channel='WEBHLS'),
        data=dict(SAMLResponse=saml_response)
    )
    return response.cookies['avs_cookie']


def hls_url(avs_cookie, channel_id):
    '''Returns the HLS stream URL for a channel'''
    if not avs_cookie:
        return None

    response = requests.get(
        'https://be.avs.bt.com/AVS/besc',
        params=dict(action='GetCDN', type='LIVE', id=channel_id, channel='WEBHLS', asJson='Y'),
        cookies=dict(avs_cookie=avs_cookie)
    )
    result = response.json()
    result_obj = result['resultObj']

    if not result_obj:
        raise BTError(result['errorDescription'], result['message'])

    return result_obj['src']


def _localise(datetime_str, timezone):
    datetime_utc = datetime(*(time.strptime(datetime_str, '%Y-%m-%dT%H:%M:%SZ')[0:6]))
    return pytz.utc.localize(datetime_utc).astimezone(pytz.timezone(timezone)).strftime('%H:%M')


def _now_and_next(channel_epg_index, timezone):
    channels_epg = requests.get('https://epg.cdn.vision.bt.com/JSON/all').json()['channels']
    channel_epg = channels_epg[channel_epg_index]
    for program in ('now', 'next'):
        data = channel_epg[program]
        yield _Program(
            title=data['title'],
            synopsis=data['synopsis'],
            start=_localise(data['start'], timezone)
        )


def epg(channel_epg_index, timezone='Europe/London'):
    'Return Electronic Program Guide information for a channel'
    return _EPG(*_now_and_next(channel_epg_index, timezone))
