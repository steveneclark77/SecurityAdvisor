from django.db import migrations


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    immutable = ['news_issueversion', 'news_issueversionreference']
    if vendor == 'sqlite':
        for table in immutable:
            for action in ['UPDATE', 'DELETE']:
                schema_editor.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Issue versions and references are immutable'); END")
        schema_editor.execute("""CREATE TRIGGER news_current_insert_guard BEFORE INSERT ON news_issue
            WHEN NEW.current_version_id IS NOT NULL BEGIN SELECT RAISE(ABORT, 'Create issue before assigning its first version'); END""")
        schema_editor.execute("""CREATE TRIGGER news_reference_sealed BEFORE INSERT ON news_issueversionreference
            WHEN EXISTS (SELECT 1 FROM news_issueversion v JOIN news_issue i ON i.id = v.issue_id
                JOIN news_issueversion latest ON latest.id = i.current_version_id
                WHERE v.id = NEW.version_id AND latest.version_number >= v.version_number)
            BEGIN SELECT RAISE(ABORT, 'Published version references are immutable'); END""")
        schema_editor.execute("""CREATE TRIGGER news_current_version_guard BEFORE UPDATE OF current_version_id ON news_issue
            WHEN NEW.current_version_id IS NOT OLD.current_version_id AND (
                NEW.current_version_id IS NULL OR NOT EXISTS (SELECT 1 FROM news_issueversion v
                    WHERE v.id = NEW.current_version_id AND v.issue_id = NEW.id
                    AND v.version_number = COALESCE((SELECT version_number FROM news_issueversion WHERE id = OLD.current_version_id), 0) + 1))
            BEGIN SELECT RAISE(ABORT, 'Invalid current version transition'); END""")
    elif vendor == 'postgresql':
        schema_editor.execute("""CREATE FUNCTION news_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Issue versions and references are immutable' USING ERRCODE = '23000'; END $$""")
        for table in immutable:
            schema_editor.execute(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION news_immutable()')
        schema_editor.execute("""CREATE FUNCTION news_reference_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM news_issueversion WHERE id = NEW.version_id) OR EXISTS (SELECT 1 FROM news_issueversion v JOIN news_issue i ON i.id = v.issue_id
                    JOIN news_issueversion latest ON latest.id = i.current_version_id
                    WHERE v.id = NEW.version_id AND latest.version_number >= v.version_number) THEN
                    RAISE EXCEPTION 'Published version references are immutable' USING ERRCODE = '23000';
                END IF;
                RETURN NEW;
            END $$""")
        schema_editor.execute('CREATE TRIGGER news_reference_sealed BEFORE INSERT ON news_issueversionreference FOR EACH ROW EXECUTE FUNCTION news_reference_guard()')
        schema_editor.execute("""CREATE FUNCTION news_current_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    IF NEW.current_version_id IS NOT NULL THEN
                        RAISE EXCEPTION 'Create issue before assigning its first version' USING ERRCODE = '23000';
                    END IF;
                    RETURN NEW;
                END IF;
                IF NEW.current_version_id IS DISTINCT FROM OLD.current_version_id AND (
                    NEW.current_version_id IS NULL OR NOT EXISTS (SELECT 1 FROM news_issueversion v
                        WHERE v.id = NEW.current_version_id AND v.issue_id = NEW.id
                        AND v.version_number = COALESCE((SELECT version_number FROM news_issueversion WHERE id = OLD.current_version_id), 0) + 1)) THEN
                    RAISE EXCEPTION 'Invalid current version transition' USING ERRCODE = '23000';
                END IF;
                RETURN NEW;
            END $$""")
        schema_editor.execute('CREATE TRIGGER news_current_version_guard BEFORE UPDATE OF current_version_id ON news_issue FOR EACH ROW EXECUTE FUNCTION news_current_guard()')
        schema_editor.execute('CREATE TRIGGER news_current_insert_guard BEFORE INSERT ON news_issue FOR EACH ROW EXECUTE FUNCTION news_current_guard()')
    else:
        raise RuntimeError('Issue version immutability requires PostgreSQL or SQLite.')


def uninstall(apps, schema_editor):
    """Synthetic database teardown helper; deliberately not a reverse migration."""
    if schema_editor.connection.vendor == 'sqlite':
        for table in ['news_issueversion', 'news_issueversionreference']:
            for action in ['update', 'delete']:
                schema_editor.execute(f'DROP TRIGGER {table}_no_{action}')
        schema_editor.execute('DROP TRIGGER news_reference_sealed')
        schema_editor.execute('DROP TRIGGER news_current_version_guard')
        schema_editor.execute('DROP TRIGGER news_current_insert_guard')
    elif schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('DROP TRIGGER news_issueversion_immutable ON news_issueversion')
        schema_editor.execute('DROP TRIGGER news_issueversionreference_immutable ON news_issueversionreference')
        schema_editor.execute('DROP TRIGGER news_reference_sealed ON news_issueversionreference')
        schema_editor.execute('DROP TRIGGER news_current_version_guard ON news_issue')
        schema_editor.execute('DROP TRIGGER news_current_insert_guard ON news_issue')
        for name in ['news_immutable', 'news_reference_guard', 'news_current_guard']:
            schema_editor.execute(f'DROP FUNCTION {name}()')


class Migration(migrations.Migration):
    dependencies = [('news', '0003_remove_issue_description_remove_issue_identifiers_and_more')]
    operations = [migrations.RunPython(install)]
