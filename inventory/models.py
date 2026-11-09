from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

FACT_STATES = [('unknown','Unknown — confirm facts'),('reported','Customer-reported'),('confirmed','Consultant-confirmed')]
ITEM_KINDS = [('operation','Business operation'),('provider','Provider / outsourced service'),('device','Device / equipment group'),('software','Software / cloud application'),('network','Network / ISP / connectivity'),('physical','Physical security / operational system'),('data','Information / data set')]
EXPOSURES = [('payments','Payment processing'),('employee_pii','Employee PII'),('customer_pii','Customer PII'),('software_development','Software development / coding agents'),('public_apps','Public applications'),('remote_access','Remote access / remote workers'),('ot','Operational technology')]


class InventoryItem(models.Model):
    customer = models.ForeignKey('engagements.Customer', on_delete=models.PROTECT, related_name='inventory_items')
    kind = models.CharField(max_length=20, choices=ITEM_KINDS)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    owner = models.CharField(max_length=200, blank=True, help_text='Responsible person/team; unknown is acceptable. Never enter credentials.')
    state = models.CharField(max_length=20, choices=FACT_STATES, default='unknown')
    provenance = models.TextField(blank=True, help_text='Who reported/confirmed these facts, evidence reference, and any limitations. Confirmation of inventory facts is not a passed security assessment.')
    last_reviewed = models.DateField(null=True, blank=True)
    archived = models.BooleanField(default=False)
    exposures = models.JSONField(default=list, blank=True)
    criticality = models.CharField(max_length=20, choices=[('unknown','Unknown'),('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')], default='unknown')
    criticality_reason = models.TextField(blank=True, help_text='Use business consequences; customer-facing, back-office, and KTLO operations have equal standing.')
    operation_category = models.CharField(max_length=20, choices=[('customer','Customer-facing'),('back_office','Back-office'),('ktlo','Infrastructure / keep the lights on'),('mixed','Mixed')], blank=True)
    schedule = models.TextField(blank=True, help_text='Frequency, deadlines, and time zone; e.g. biweekly payroll or monthly rent.')
    critical_windows = models.TextField(blank=True, help_text='When interruption has elevated impact, such as payroll submission cutoff.')
    outage_tolerance = models.TextField(blank=True)
    acceptable_data_loss = models.TextField(blank=True)
    workaround = models.TextField(blank=True)
    financial_impact = models.TextField(blank=True)
    availability_impact = models.TextField(blank=True)
    reputation_impact = models.TextField(blank=True)
    other_impact = models.TextField(blank=True, help_text='Privacy, safety, contractual or legal consequences where applicable.')
    impact = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1),MaxValueValidator(5)])
    quantity = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)], help_text='Individual devices or a counted group; leave blank if unknown.')
    location = models.CharField(max_length=200, blank=True)
    vendor_product = models.CharField(max_length=200, blank=True)
    operating_system = models.CharField(max_length=200, blank=True)
    support_status = models.CharField(max_length=200, blank=True)
    security_configuration = models.TextField(blank=True, help_text='Reported/confirmed antivirus, firewall, encryption, management, bundled security, etc. Unknown configuration is not a failed or passed safeguard.')
    access_method = models.TextField(blank=True, help_text='Sign-in path, SSO/separate account, remote/vendor access. No passwords, tokens, or keys.')
    data_handling = models.TextField(blank=True, help_text='Data categories, storage and transfer locations, retention, and provider responsibilities. Distinguish full card data, masked references, and tokens; record uncertainty.')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name','pk']

    def __str__(self):
        return f'{self.name} ({self.get_kind_display()})'

    def clean(self):
        super().clean()
        if self.state != 'unknown' and not self.provenance.strip():
            raise ValidationError('Reported/confirmed facts require provenance; otherwise keep them unknown.')
        if self.state == 'confirmed' and not self.last_reviewed:
            raise ValidationError('Record the review date for confirmed facts.')
        if self.criticality != 'unknown' and not self.criticality_reason.strip():
            raise ValidationError('Explain business criticality without privileging an operation category.')
        if self.exposures is not None and (not isinstance(self.exposures,list) or not set(self.exposures).issubset(dict(EXPOSURES))):
            raise ValidationError('Select supported exposure categories.')


class InventoryConnection(models.Model):
    customer = models.ForeignKey('engagements.Customer', on_delete=models.PROTECT, related_name='inventory_connections')
    source = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='outgoing')
    target = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='incoming')
    relationship = models.CharField(max_length=25, choices=[('depends_on','Depends on'),('provided_by','Provided by'),('uses','Uses'),('stores','Stores / handles'),('transfers_to','Transfers data to'),('accesses_via','Accesses via'),('connected_to','Connected to'),('protects','Protects')])
    details = models.TextField(help_text='Direction, information exchanged, integration, or dependency; no credentials.')
    access_method = models.TextField(blank=True, help_text='API, file exchange, portal, vendor remote support, authentication method; no secrets.')
    state = models.CharField(max_length=20, choices=FACT_STATES, default='unknown')
    provenance = models.TextField(blank=True)
    last_reviewed = models.DateField(null=True, blank=True)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['pk']
        constraints = [models.CheckConstraint(condition=~models.Q(source=models.F('target')),name='inventory_connection_different_endpoints')]

    def clean(self):
        super().clean()
        if self.source_id and self.target_id:
            if self.source_id == self.target_id:
                raise ValidationError('Connect two different records.')
            if self.source.customer_id != self.customer_id or self.target.customer_id != self.customer_id:
                raise ValidationError('Both connection endpoints must belong to this customer.')
        if self.state != 'unknown' and not self.provenance.strip():
            raise ValidationError('Reported/confirmed connections require provenance.')
        if self.state == 'confirmed' and not self.last_reviewed:
            raise ValidationError('Record when the connection was confirmed.')


class InventoryFollowUp(models.Model):
    customer = models.ForeignKey('engagements.Customer', on_delete=models.PROTECT, related_name='inventory_followups')
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, null=True, blank=True)
    source_intake = models.OneToOneField('engagements.Intake',on_delete=models.PROTECT,null=True,blank=True)
    question = models.TextField(help_text='Missing environment facts, not a verdict on a safeguard.')
    owner = models.CharField(max_length=200, blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('open','Open — information needed'),('resolved','Resolved with response')], default='open')
    response = models.TextField(blank=True)

    def clean(self):
        super().clean()
        if self.item_id and self.item.customer_id != self.customer_id:
            raise ValidationError('The related record must belong to this customer.')
        if self.source_intake_id and self.source_intake.engagement.customer_id != self.customer_id:
            raise ValidationError('Intake must belong to this customer.')
        if self.status == 'resolved' and not self.response.strip():
            raise ValidationError('Record the confirmed information or explain the resolution.')


class InventoryEvent(models.Model):
    customer = models.ForeignKey('engagements.Customer',on_delete=models.PROTECT,related_name='inventory_events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True)
    description = models.CharField(max_length=250)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self,*args,**kwargs):
        if self.pk:
            raise ValidationError('Inventory history is append-only.')
        super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):
        raise ValidationError('Inventory history must be preserved.')
