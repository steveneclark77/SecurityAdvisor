from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('engagements','0004_actionresult_followup_due_and_more')]
    operations = [
        migrations.RenameField(model_name='engagement', old_name='contact', new_name='legacy_contact_note'),
        migrations.AlterField(model_name='engagement', name='legacy_contact_note', field=models.CharField(max_length=200, blank=True, help_text='Preserved original free-text contact; review and create structured contacts.')),
    ]
