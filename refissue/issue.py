# -*- coding: utf-8 -*-

import logging
import os
import urllib
import json

import settings

from refissue.auth import get_token
from refissue.morpheme import MorphemeAnalyzer
from refissue.similarity import document_similarity
from refissue.github_api import request_to_github
from refissue.util import save_by, fetch_by


class Issue(object):
    u""" Model of GitHub Issues """

    _temporary_store_key = '{owner}:{repo}'
    _temporary_store_expire = 3600

    def __init__(self, id, number, title, body):
        self.id = id
        self.number = number
        self.title = title
        self.body = body
        self.keywords = _analyzer.pickup_keywords(
            self.title + ' ' + self.body
            )

    @classmethod
    def from_dict(cls, issue_dict):
        id = issue_dict.get('id')
        number = issue_dict.get('number')
        title = issue_dict.get('title')
        body = issue_dict.get('body')
        return cls(id, number, title, body)

    @classmethod
    def fetch_issues(cls, owner, repo, ignore_cache=False):
        key = cls._temporary_store_key.format(owner=owner, repo=repo)
        issues = fetch_by(key)
        if issues is None or ignore_cache:
            url = 'https://api.github.com/repos/%s/%s/issues' % (owner, repo)
            params = {
                'per_page': settings.MAX_COMPARE_ISSUES,
                'sort': 'created',
                'order': 'desc'
            }
            url += '?' + urllib.urlencode(params)
            token = get_token()

            resp, content = request_to_github(token, 'GET', url)
            if int(resp.get('status')) == 200:
                issues_dict = json.loads(content)
                issues = [Issue.from_dict(issue) for issue in issues_dict]
            else:
                logging.error('Failed to fetch issues.')
                logging.error(resp)
                logging.error(content)
                issues = None
            save_by(key, issues, time=cls._temporary_store_expire)
        return issues

    def save(self, owner, repo):
        key = self._temporary_store_key.format(owner=owner, repo=repo)
        issues = fetch_by(key)
        if issues and type(issues) == list:
            issues = [issue for issue in issues if issue.id != self.id]
            issues.append(self)
        else:
            issues = [self]
        save_by(key, issues, time=self._temporary_store_expire)

    def search_most_similar_issues(self, issues, n):
        # exclude self issue from issues
        issues = [issue for issue in issues if issue.id != self.id]
        if len(issues) == 0:
            return []
        results = [(self.compare(issue), issue) for issue in issues]
        results.sort(cmp=lambda a, b: cmp(a[0], b[0]))
        results.reverse()
        return results[0:n]

    def compare(self, other):
        return document_similarity(self.keywords, other.keywords)


_analyzer = MorphemeAnalyzer(
    os.path.join(os.path.dirname(__file__), 'ipadic-gae')
    )
