from django.contrib import admin
from .models import (
    UserProfile, 
    Document, 
    Case, 
    LegalStory, 
    Note, 
    LegalCase,
    Person,
    CaseParticipant,
    DocumentExtractedFact,
    LegalStoryCaseLink,
    DocumentCaseLink,
    Notice  # ⬅️ این خط اضافه شد
)

admin.site.register(UserProfile)
admin.site.register(Document)
admin.site.register(Case)
admin.site.register(LegalStory)
admin.site.register(Note)
admin.site.register(LegalCase)
admin.site.register(Person)
admin.site.register(CaseParticipant)
admin.site.register(DocumentExtractedFact)
admin.site.register(LegalStoryCaseLink)
admin.site.register(DocumentCaseLink)
admin.site.register(Notice)  