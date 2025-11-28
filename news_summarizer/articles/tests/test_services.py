from django.test import TestCase, override_settings
from unittest import mock
from django.utils import timezone
from models import Article
from services import fetch_and_store_articles
import requests

class ServicesTests(TestCase):
	"""
	Tests for article services.
	"""
	def test_fetch_and_store_articles_saves_new_articles(self):
		"""
		Test that fetch_and_store_articles fetches and saves new articles.
		"""
		

		fake_article = {
			'url': 'https://example.com/new-1',
			'title': 'New Article',
			'content': 'Content here',
			'publishedAt': '2020-01-01T12:00:00Z',
			'source': {'name': 'Example'}
		}

		fake_response = mock.Mock()
		fake_response.raise_for_status = mock.Mock()
		fake_response.json.return_value = {'articles': [fake_article]}

		with override_settings(NEWS_API_URL='https://api.test', NEWS_API_KEY='key', NEWS_API_QUERY='q'):
			with mock.patch('news_summarizer.articles.services.requests.get', return_value=fake_response):
				saved = fetch_and_store_articles()

		self.assertEqual(saved, 1)
		self.assertEqual(Article.objects.count(), 1)
		a = Article.objects.first()
		self.assertEqual(a.url, fake_article['url'])
		self.assertEqual(a.title, fake_article['title'])

	def test_fetch_and_store_articles_handles_request_exception(self):
		"""
		Test that fetch_and_store_articles handles RequestException gracefully.
		"""

		with override_settings(NEWS_API_URL='https://api.test', NEWS_API_KEY='key', NEWS_API_QUERY='q'):
			with mock.patch('news_summarizer.articles.services.requests.get', side_effect=requests.exceptions.RequestException("fail")):
				result = fetch_and_store_articles()

		self.assertIsNone(result)

	def test_fetch_and_store_articles_skips_existing_article(self):
		"""
		Test that fetch_and_store_articles skips articles with existing URLs.
		"""

		# create existing article with same URL
		existing = Article.objects.create(
			title='Existing',
			content='Old',
			url='https://example.com/existing',
			published_date=timezone.now(),
			source='Example'
		)

		fake_article = {
			'url': existing.url,
			'title': 'Existing Updated',
			'content': 'Content here',
			'publishedAt': '2020-01-01T12:00:00Z',
			'source': {'name': 'Example'}
		}

		fake_response = mock.Mock()
		fake_response.raise_for_status = mock.Mock()
		fake_response.json.return_value = {'articles': [fake_article]}

		with override_settings(NEWS_API_URL='https://api.test', NEWS_API_KEY='key', NEWS_API_QUERY='q'):
			with mock.patch('news_summarizer.articles.services.requests.get', return_value=fake_response):
				saved = fetch_and_store_articles()

		# No new articles saved because URL existed
		self.assertEqual(saved, 0)
		self.assertEqual(Article.objects.count(), 1)