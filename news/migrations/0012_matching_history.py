from django.db import migrations

TABLES=['news_embeddingcache','news_matchcomparison','news_calibrationversion','news_matchassessment',
        'news_matchdecision','news_matchfeedback','news_matchingconfigurationevent','news_inboxevent']


def seed(apps,schema_editor):
    apps.get_model('news','MatchingConfiguration').objects.get_or_create(pk=1)
    Event=apps.get_model('news','InboxEvent')
    decided=apps.get_model('news','ProposalDecision').objects.values('proposal_id')
    for proposal in apps.get_model('news','IssueProposal').objects.exclude(pk__in=decided).iterator():
        Event.objects.get_or_create(key=f'pending:{proposal.pk}',defaults={'kind':'pending','proposal_id':proposal.pk,
            'title':proposal.content.get('name','Potential security issue')[:500]})


def install(apps,schema_editor):
    for table in TABLES:
        if schema_editor.connection.vendor=='sqlite':
            for action in ['UPDATE','DELETE']:
                schema_editor.execute(f"CREATE TRIGGER {table}_history_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'Matching history is immutable'); END")
        elif schema_editor.connection.vendor=='postgresql':
            schema_editor.execute(f'CREATE TRIGGER {table}_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION news_immutable()')
        else:
            raise RuntimeError('Matching history requires PostgreSQL or SQLite.')

    if schema_editor.connection.vendor=='sqlite':
        for table in ['news_embeddingattempt','news_digestdelivery']:
            schema_editor.execute(f"CREATE TRIGGER {table}_retained BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT,'Operational history is retained'); END")
        schema_editor.execute("""CREATE TRIGGER news_embeddingattempt_sealed BEFORE UPDATE ON news_embeddingattempt
            WHEN OLD.status IN ('succeeded','failed') OR NEW.key IS NOT OLD.key OR NEW.model IS NOT OLD.model
            OR NEW.content_hash IS NOT OLD.content_hash OR NEW.reserved_cents IS NOT OLD.reserved_cents OR NEW.started_at IS NOT OLD.started_at
            BEGIN SELECT RAISE(ABORT,'Embedding attempt identity and finished history are immutable'); END""")
        schema_editor.execute("""CREATE TRIGGER news_digestdelivery_sealed BEFORE UPDATE ON news_digestdelivery
            WHEN OLD.status IN ('sent','skipped') OR (OLD.attempted_at IS NOT NULL AND (
            NEW.day IS NOT OLD.day OR NEW.first_event_id IS NOT OLD.first_event_id OR NEW.last_event_id IS NOT OLD.last_event_id
            OR NEW.payload IS NOT OLD.payload OR NEW.created_at IS NOT OLD.created_at))
            BEGIN SELECT RAISE(ABORT,'Digest delivery input and completed history are immutable'); END""")
    elif schema_editor.connection.vendor=='postgresql':
        schema_editor.execute("""CREATE FUNCTION news_matching_operational_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP='DELETE' THEN
                    RAISE EXCEPTION 'Operational history is retained' USING ERRCODE='23000';
                END IF;
                IF TG_TABLE_NAME='news_embeddingattempt' THEN
                    IF OLD.status IN ('succeeded','failed') OR (NEW.key,NEW.model,NEW.content_hash,NEW.reserved_cents,NEW.started_at)
                        IS DISTINCT FROM (OLD.key,OLD.model,OLD.content_hash,OLD.reserved_cents,OLD.started_at) THEN
                        RAISE EXCEPTION 'Embedding attempt identity and finished history are immutable' USING ERRCODE='23000';
                    END IF;
                ELSE
                    IF OLD.status IN ('sent','skipped') OR (OLD.attempted_at IS NOT NULL AND
                        (NEW.day,NEW.first_event_id,NEW.last_event_id,NEW.payload,NEW.created_at) IS DISTINCT FROM
                        (OLD.day,OLD.first_event_id,OLD.last_event_id,OLD.payload,OLD.created_at)) THEN
                        RAISE EXCEPTION 'Digest input and completed history are immutable' USING ERRCODE='23000';
                    END IF;
                END IF;
                RETURN NEW;
            END $$""")
        for table in ['news_embeddingattempt','news_digestdelivery']:
            schema_editor.execute(f'CREATE TRIGGER {table}_operational BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION news_matching_operational_guard()')


def uninstall(apps,schema_editor):
    for table in TABLES:
        if schema_editor.connection.vendor=='sqlite':
            for action in ['update','delete']:
                schema_editor.execute(f'DROP TRIGGER {table}_history_{action}')
        elif schema_editor.connection.vendor=='postgresql':
            schema_editor.execute(f'DROP TRIGGER {table}_history ON {table}')

    if schema_editor.connection.vendor=='sqlite':
        for table in ['news_embeddingattempt','news_digestdelivery']:
            schema_editor.execute(f'DROP TRIGGER {table}_retained')
            schema_editor.execute(f'DROP TRIGGER {table}_sealed')
    elif schema_editor.connection.vendor=='postgresql':
        for table in ['news_embeddingattempt','news_digestdelivery']:
            schema_editor.execute(f'DROP TRIGGER {table}_operational ON {table}')
        schema_editor.execute('DROP FUNCTION news_matching_operational_guard()')


class Migration(migrations.Migration):
    dependencies=[('news','0011_digestdelivery_embeddingattempt_embeddingcache_and_more')]
    operations=[migrations.RunPython(seed),migrations.RunPython(install)]
