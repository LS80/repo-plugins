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
Module for extracting video links from the BT Sport website
'''

from urlparse import urljoin
from datetime import datetime
import time
from collections import namedtuple
import math
import re
import ast

import requests


CATEGORIES_URL = 'http://sport.bt.com/all-videos/videos-01364228997406'
API_URL = 'http://api-search.sport.bt.com/search/sport/select'

_Video = namedtuple('Video', 'title description url thumbnail date duration')
_Category = namedtuple('Category', 'title path')


def _date_from_str(date_str):
    '''Returns a data object from a string.
       datetime.strptime is avoided due to an issue with Python in Kodi.
       Ignores possible milliseconds part by including only 19 characters.'''
    return datetime(*(time.strptime(date_str[:19], '%Y-%m-%dT%H:%M:%S')[0:6])).date()


def categories():
    '''Generator for all sport categories on the website'''
    html = requests.get(CATEGORIES_URL).text
    match = re.search(r'BTSPORT\.cms\.videohub\.pagedetails = (.*?)\t', html, re.DOTALL)
    pagedetails = ast.literal_eval(match.group(1))
    yield  _Category(title=None, path=pagedetails['defaultpage']['pageurl'])
    for category in pagedetails['pages']:
        yield _Category(title=category['title'], path=category['pageurl'])


def query_text(path):
    '''Returns the API query for a category path'''
    html = requests.get(urljoin('http://sport.bt.com/', path)).text
    match = re.search(r'BTSPORT\.cms\.videohub\.properties = (.*?)\t', html, re.DOTALL)
    properties = ast.literal_eval(match.group(1))
    if not properties['tags']:
        return None

    properties['tags'] = ','.join('"{}"'.format(tag) for tag in properties['tags'].split(','))
    query_fmt = 'tags:({tags})'
    if 'competition' in properties:
        query_fmt += ' OR (ccategory:("{ccategory}") AND competition:("{competition}"))'
    elif 'ccategory' in properties:
        query_fmt += ' OR ccategory:("{ccategory}")'
    return query_fmt.format(**properties)


def _videos(videos_response):
    for video in videos_response['docs']:
        yield _Video(
            title=video['h1title'],
            description=video['teaser'],
            url=video.get('hlsurl') or video.get('streamingurl'),
            thumbnail=video.get('imageurl') or video.get('thumbnailURL'),
            date=video.get('publicationdate') and _date_from_str(video['publicationdate']),
            duration=video.get('duration') and int(video['duration'])
        )


def video_results(query, page=1, page_size=10):
    '''Returns a generator for videos matching a query, and the number of pages of results'''
    params = dict(
        q='AssetType:(BTVideo)',
        fq=['Publist:btsport'],
        sort='publicationdate desc',
        wt='json',
        start=(page - 1) * page_size,
        rows=page_size
    )
    params['fq'].append(query)
    videos_response = requests.get(API_URL, params=params).json()['response']
    num_pages = int(math.ceil(float(videos_response['numFound']) / page_size))
    return _videos(videos_response), num_pages


def search_results(term, page=1, page_size=10):
    '''Returns a generator for video search results, and the number of pages of results'''
    return video_results('text:("{}")'.format(term), page, page_size)
