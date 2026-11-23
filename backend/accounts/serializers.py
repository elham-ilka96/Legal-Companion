from rest_framework import serializers
from .models import UserProfile, LegalCase, Note

from .models import UserProfile, LegalCase, Note, Document, LegalStory


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'


class LegalCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalCase
        fields = '__all__'

        from .models import UserProfile, LegalCase, Note

class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ['id', 'title', 'body', 'created_at', 'updated_at']




# ... (کدهای قبلی UserProfileSerializer, LegalCaseSerializer, NoteSerializer را دست نزنید) ...

class LegalStorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalStory
        fields = ['id', 'title', 'user_context', 'current_summary', 'summary_revision', 'story_status', 'created_at']

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'original_filename', 'current_summary', 'processing_status', 'created_at']
        