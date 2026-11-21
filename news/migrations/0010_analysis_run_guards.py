from django.db import migrations


def install(apps,schema_editor):
    if schema_editor.connection.vendor=='sqlite':
        schema_editor.execute("""CREATE TRIGGER news_analysisrun_retained BEFORE DELETE ON news_analysisrun
            BEGIN SELECT RAISE(ABORT,'Analysis attempts cannot be deleted'); END""")
        schema_editor.execute("""CREATE TRIGGER news_analysisrun_sealed BEFORE UPDATE ON news_analysisrun
            WHEN OLD.status IN ('succeeded','failed') OR (OLD.status='running' AND (
            NEW.revision_id IS NOT OLD.revision_id OR NEW.policy_key IS NOT OLD.policy_key OR
            NEW.model IS NOT OLD.model OR NEW.prompt_version IS NOT OLD.prompt_version OR
            NEW.schema_version IS NOT OLD.schema_version OR NEW.attempt IS NOT OLD.attempt OR
            NEW.input_snapshot IS NOT OLD.input_snapshot OR NEW.reserved_cents IS NOT OLD.reserved_cents OR
            NEW.started_at IS NOT OLD.started_at OR NEW.status NOT IN ('succeeded','failed')))
            BEGIN SELECT RAISE(ABORT,'Analysis input and finished attempts are immutable'); END""")
    elif schema_editor.connection.vendor=='postgresql':
        schema_editor.execute("""CREATE FUNCTION news_analysisrun_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP='DELETE' THEN
                    RAISE EXCEPTION 'Analysis attempts cannot be deleted' USING ERRCODE='23000';
                END IF;
                IF OLD.status IN ('succeeded','failed') OR (OLD.status='running' AND (
                    (NEW.revision_id,NEW.policy_key,NEW.model,NEW.prompt_version,NEW.schema_version,
                     NEW.attempt,NEW.input_snapshot,NEW.reserved_cents,NEW.started_at) IS DISTINCT FROM
                    (OLD.revision_id,OLD.policy_key,OLD.model,OLD.prompt_version,OLD.schema_version,
                     OLD.attempt,OLD.input_snapshot,OLD.reserved_cents,OLD.started_at)
                    OR NEW.status NOT IN ('succeeded','failed'))) THEN
                    RAISE EXCEPTION 'Analysis input and finished attempts are immutable' USING ERRCODE='23000';
                END IF;
                RETURN NEW;
            END $$""")
        schema_editor.execute('CREATE TRIGGER news_analysisrun_sealed BEFORE UPDATE OR DELETE ON news_analysisrun FOR EACH ROW EXECUTE FUNCTION news_analysisrun_guard()')


def uninstall(apps,schema_editor):
    if schema_editor.connection.vendor=='sqlite':
        schema_editor.execute('DROP TRIGGER news_analysisrun_retained')
        schema_editor.execute('DROP TRIGGER news_analysisrun_sealed')
    else:
        schema_editor.execute('DROP TRIGGER news_analysisrun_sealed ON news_analysisrun')
        schema_editor.execute('DROP FUNCTION news_analysisrun_guard()')


class Migration(migrations.Migration):
    dependencies=[('news','0009_article_current_revision')]
    operations=[migrations.RunPython(install)]
