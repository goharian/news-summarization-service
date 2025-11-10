from rest_framework import generics
from .models import Article
from .serializers import ArticleSerializer

class ArticleListCreateView(generics.ListCreateAPIView):
    queryset = Article.objects.all().order_by('-publishedDate')
    serializer_class = ArticleSerializer
