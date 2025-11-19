from django.test import TestCase, override_settings
from django.core.cache import caches
from unittest import mock
import sys
import types

from . import chatgpt_service


class ChatGPTServiceTests(TestCase):
	def test_summarize_returns_mock_when_no_api_key(self):
		# Ensure function falls back to mock summary when OPENAI_API_KEY is missing
		with override_settings(OPENAI_API_KEY=None):
			summary = chatgpt_service.summarize_article_with_chatgpt(
				title="Test Title",
				content="Some content goes here."
			)

		self.assertIn("**Mock Summary:**", summary)

	def test_summarize_uses_openai_client_and_returns_text(self):
		# Create a fake openai module with OpenAI and APIError
		fake_module = types.ModuleType("openai")

		class FakeResponses:
			def create(self, *args, **kwargs):
				class Resp:
					output_text = "This is a concise summary."

				return Resp()

		class FakeClient:
			def __init__(self, api_key=None):
				self.responses = FakeResponses()

		fake_module.OpenAI = FakeClient
		fake_module.APIError = Exception

		# Inject fake module into sys.modules so the function import finds it
		with mock.patch.dict(sys.modules, {"openai": fake_module}):
			with override_settings(OPENAI_API_KEY="sk-test"):
				summary = chatgpt_service.summarize_article_with_chatgpt(
					title="Tech News",
					content="Lots of interesting content."
				)

		self.assertEqual(summary, "This is a concise summary.")

	def test_get_article_summary_with_caching_uses_cache(self):
		# Use a local-memory cache for tests and patch module SUMMARY_CACHE
		test_caches = {
			"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
			"summaries": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
		}

		with override_settings(CACHES=test_caches):
			# reload caches to pick up override_settings
			caches._connections = {}
			# point the module SUMMARY_CACHE to the test summaries cache
			chatgpt_service.SUMMARY_CACHE = caches["summaries"]

			# patch the summarizer to return a known value
			with mock.patch(
				"news_summarizer.articles.chatgpt_service.summarize_article_with_chatgpt",
				return_value="Cached summary"
			):
				# first call should compute and store in cache
				summary1, from_cache1 = chatgpt_service.get_article_summary_with_caching(
					"Caching Title", "Content"
				)

				self.assertFalse(from_cache1)
				self.assertEqual(summary1, "Cached summary")

				# second call should hit cache and return same value with flag True
				summary2, from_cache2 = chatgpt_service.get_article_summary_with_caching(
					"Caching Title", "Different content should be ignored for key"
				)

				self.assertTrue(from_cache2)
				self.assertEqual(summary2, "Cached summary")


class ArticleViewsTests(TestCase):
	def test_article_summary_view_returns_summary_and_cached_flag(self):
		from django.utils import timezone
		from .models import Article

		# Create an article in the test database
		article = Article.objects.create(
			title="View Test",
			content="Some content for the view test",
			url="https://example.com/article",
			published_date=timezone.now(),
			source="Example"
		)

		# Patch the function imported in the views module
		with mock.patch(
			"news_summarizer.articles.views.get_article_summary_with_caching",
			return_value=("View summary", True)
		):
			client = self.client
			resp = client.get(f"/articles/{article.pk}/summary")

		self.assertEqual(resp.status_code, 200)
		data = resp.json()
		self.assertEqual(data.get("summary"), "View summary")
		self.assertTrue(data.get("cached"))


class ServicesTests(TestCase):
	def test_fetch_and_store_articles_saves_new_articles(self):
		from django.utils import timezone
		from .models import Article
		from .services import fetch_and_store_articles
		import requests

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
		from .services import fetch_and_store_articles
		import requests

		with override_settings(NEWS_API_URL='https://api.test', NEWS_API_KEY='key', NEWS_API_QUERY='q'):
			with mock.patch('news_summarizer.articles.services.requests.get', side_effect=requests.exceptions.RequestException("fail")):
				result = fetch_and_store_articles()

		self.assertIsNone(result)

	def test_fetch_and_store_articles_skips_existing_article(self):
		from django.utils import timezone
		from .models import Article
		from .services import fetch_and_store_articles

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

