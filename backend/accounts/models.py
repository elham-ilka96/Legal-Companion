import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

# =========================================================
# ۱. مدل‌های قبلی (برای اجرای برنامه فعلی)
# =========================================================

class UserProfile(models.Model):
    full_name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=15, unique=True)
    national_id = models.CharField(max_length=20, blank=True, null=True)
    age = models.CharField(max_length=10, blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    height = models.CharField(max_length=10, blank=True, null=True)
    weight = models.CharField(max_length=10, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    password_hash = models.CharField(max_length=255, blank=True, null=True)
    diseases = models.JSONField(default=list, blank=True)
    disease_details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class LegalCase(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, null=True, blank=True)
    case_number = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    topic = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=50, default="active")
    court = models.CharField(max_length=255, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    plaintiff = models.CharField(max_length=255, blank=True, null=True)
    defendants = models.CharField(max_length=255, blank=True, null=True)
    demands = models.CharField(max_length=255, blank=True, null=True)
    file_hash = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.case_number}"


class VerificationCode(models.Model):
    mobile = models.CharField(max_length=15)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.mobile


class AuthSession(models.Model):
    token_hash = models.CharField(max_length=64, unique=True)
    mobile = models.CharField(max_length=15)
    mode = models.CharField(max_length=20, choices=[('signup', 'ثبت نام'), ('login', 'ورود')])
    expires_at = models.DateTimeField()

    def __str__(self):
        return self.mobile


class VerificationRateLimit(models.Model):
    mobile = models.CharField(max_length=15, unique=True)
    sent_at = models.DateTimeField()

    def __str__(self):
        return self.mobile


class Note(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='notes')
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


# =========================================================
# ۲. مدل‌های جدید (طبق طرح تفهیم)
# =========================================================

class LegalStory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='legal_stories')
    title = models.CharField(max_length=255)
    user_context = models.TextField(blank=True, null=True)
    current_summary = models.TextField(blank=True, null=True)
    summary_revision = models.IntegerField(default=1)
    story_status = models.CharField(max_length=50, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='documents')
    external_document_id = models.CharField(max_length=100, blank=True, null=True)
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    file_size_bytes = models.BigIntegerField(blank=True, null=True)
    sha256_hash = models.CharField(max_length=64, unique=True)
    current_summary = models.TextField(blank=True, null=True)
    processing_status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_filename


class AIProcessingRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    task_type = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    status = models.CharField(max_length=50)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class Case(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='cases_new')
    case_number_raw = models.CharField(max_length=100, blank=True, null=True)
    case_number_normalized = models.CharField(max_length=100, blank=True, null=True)
    court_name = models.CharField(max_length=255, blank=True, null=True)
    case_type = models.CharField(max_length=100, blank=True, null=True)
    current_summary = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Case {self.case_number_raw}"


class LegalStoryCaseLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_story = models.ForeignKey(LegalStory, on_delete=models.CASCADE, related_name='case_links')
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='story_links')
    created_at = models.DateTimeField(auto_now_add=True)


class DocumentCaseLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='case_links')
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='document_links')
    created_at = models.DateTimeField(auto_now_add=True)


class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='persons')
    display_name = models.CharField(max_length=255)
    normalized_name = models.CharField(max_length=255, blank=True, null=True)
    person_status = models.CharField(max_length=50, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name


class CaseParticipant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='participants')
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='case_roles')
    role = models.CharField(max_length=100)  # مثلا: plaintiff, defendant, lawyer
    role_raw = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CaseEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=100, blank=True, null=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    event_date = models.DateField(null=True, blank=True)
    event_date_raw = models.CharField(max_length=100, blank=True, null=True)
    event_status = models.CharField(max_length=50, default='confirmed')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
# =========================================================
# ۶. جداول تکمیلی (فیلدهای استخراج‌شده، نسخه‌های خلاصه، اشخاص، تطبیق)
# =========================================================

class DocumentExtractedFact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='extracted_facts')
    field_key = models.CharField(max_length=100) # مثلا: judgment_number
    value_raw = models.TextField(blank=True, null=True)
    value_normalized = models.TextField(blank=True, null=True)
    confidence = models.FloatField(default=1.0)
    is_current = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.field_key} - {self.document.original_filename}"

class DocumentSummaryVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='summary_versions')
    revision = models.IntegerField(default=1)
    summary_text = models.TextField()
    approval_status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

class PersonAlias(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='aliases')
    alias_raw = models.CharField(max_length=255)
    alias_normalized = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.alias_raw} (برای {self.person.display_name})"

class CaseStoryMatchCandidate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='story_candidates')
    legal_story = models.ForeignKey(LegalStory, on_delete=models.CASCADE, related_name='case_candidates')
    score = models.FloatField(default=0.0)
    rationale = models.TextField(blank=True, null=True) 
    status = models.CharField(max_length=50, default='pending') 
    created_at = models.DateTimeField(auto_now_add=True)

class DocumentCaseReference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='case_references')
    referenced_case_number_raw = models.CharField(max_length=100, blank=True, null=True)
    referenced_case = models.ForeignKey(Case, on_delete=models.SET_NULL, null=True, blank=True, related_name='document_references')
    reference_type = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)    
# =========================================================
# ۷. مدل‌های باقی‌مانده (طبق فایل تفهیم - اعلان‌ها، تنظیمات، تاریخچه)
# =========================================================

class UserSettings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='settings')
    locale = models.CharField(max_length=10, default='fa')
    timezone = models.CharField(max_length=50, default='Asia/Tehran')
    calendar_preference = models.CharField(max_length=10, default='jalali')

class DocumentPersonMention(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='person_mentions')
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True)
    mentioned_name_raw = models.CharField(max_length=255)
    normalized_name = models.CharField(max_length=255, blank=True, null=True)
    role_in_document = models.CharField(max_length=100, blank=True, null=True)
    source_page = models.IntegerField(null=True, blank=True)
    confidence = models.FloatField(default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)

class EventDocumentLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(CaseEvent, on_delete=models.CASCADE, related_name='document_links')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='event_links')
    evidence_role = models.CharField(max_length=50, default='supporting')
    source_page = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class EventDateObservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(CaseEvent, on_delete=models.CASCADE, related_name='date_observations')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='date_observations')
    observed_date = models.DateField(null=True, blank=True)
    observed_date_raw = models.CharField(max_length=100, blank=True, null=True)
    calendar_system = models.CharField(max_length=20, default='jalali')
    source_page = models.IntegerField(null=True, blank=True)
    confidence = models.FloatField(default=1.0)
    selection_status = models.CharField(max_length=50, default='candidate')
    created_at = models.DateTimeField(auto_now_add=True)

class CaseMatchFeature(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='match_features')
    feature_type = models.CharField(max_length=100)
    normalized_value = models.CharField(max_length=255)
    display_value = models.CharField(max_length=255)
    confidence = models.FloatField(default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)

class CaseStateVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='state_versions')
    revision = models.IntegerField(default=1)
    state_payload = models.JSONField(default=dict)
    change_reason = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class CaseSummaryVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='summary_versions')
    revision = models.IntegerField(default=1)
    summary_text = models.TextField()
    approval_status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

class StorySummaryVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_story = models.ForeignKey(LegalStory, on_delete=models.CASCADE, related_name='summary_versions')
    revision = models.IntegerField(default=1)
    summary_text = models.TextField()
    approval_status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

class UserReviewDecision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='review_decisions')
    target_type = models.CharField(max_length=50) # document, case, story, event, person
    target_id = models.UUIDField()
    decision = models.CharField(max_length=50) # accepted, rejected, modified
    previous_value = models.JSONField(null=True, blank=True)
    accepted_value = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class DuplicateDocumentCandidate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='duplicate_candidates')
    candidate_document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='duplicate_of')
    similarity_score = models.FloatField(default=0.0)
    status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

# =========================================================
# ۸. مدل‌های اعلان و یادآوری
# =========================================================

class NotificationPreference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='notification_preferences')
    notification_type = models.CharField(max_length=100)
    channel = models.CharField(max_length=50) # email, sms, push, in_app
    enabled = models.BooleanField(default=True)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Reminder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='reminders')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    due_at = models.DateTimeField()
    timezone = models.CharField(max_length=50, default='Asia/Tehran')
    related_case = models.ForeignKey(Case, on_delete=models.SET_NULL, null=True, blank=True)
    related_document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    related_event = models.ForeignKey(CaseEvent, on_delete=models.SET_NULL, null=True, blank=True)
    reminder_status = models.CharField(max_length=50, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    body = models.TextField()
    severity = models.CharField(max_length=20, default='info')
    status = models.CharField(max_length=50, default='unread')
    related_case = models.ForeignKey(Case, on_delete=models.SET_NULL, null=True, blank=True)
    related_document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    reminder = models.ForeignKey(Reminder, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

class NotificationDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='deliveries')
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    channel = models.CharField(max_length=50) # email, sms, push
    destination_masked = models.CharField(max_length=255, blank=True, null=True)
    delivery_status = models.CharField(max_length=50, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class NotificationDeliveryAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery = models.ForeignKey(NotificationDelivery, on_delete=models.CASCADE, related_name='attempts')
    attempt_number = models.IntegerField(default=1)
    attempt_status = models.CharField(max_length=50, default='pending')
    error_message = models.TextField(blank=True, null=True)
    attempted_at = models.DateTimeField(auto_now_add=True)

class UserPushDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='push_devices')
    platform = models.CharField(max_length=50) # ios, android, web
    token_encrypted = models.TextField()
    device_label = models.CharField(max_length=100, blank=True, null=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

class NotificationOutbox(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=100)
    aggregate_type = models.CharField(max_length=100)
    aggregate_id = models.UUIDField()
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, null=True, blank=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=50, default='pending')
    attempts = models.IntegerField(default=0)
    available_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.UUIDField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)    
class Notice(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='notices')
    document_title = models.CharField(max_length=255, verbose_name="عنوان سند")
    story_title = models.CharField(max_length=255, blank=True, null=True, verbose_name="عنوان داستان")
    
    # تاریخ و ساعت ثبت ابلاغیه
    date = models.CharField(max_length=50, blank=True, null=True, verbose_name="تاریخ ثبت")
    time = models.CharField(max_length=50, blank=True, null=True, verbose_name="ساعت ثبت")
    
    # وضعیت فعال بودن (مهلت اعتراض)
    is_active = models.BooleanField(default=True, verbose_name="فعال است")
    
    # اطلاعات جلسه
    hearing_date = models.CharField(max_length=100, blank=True, null=True, verbose_name="تاریخ جلسه")
    hearing_time = models.CharField(max_length=100, blank=True, null=True, verbose_name="ساعت جلسه")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document_title} - {self.user.full_name}"