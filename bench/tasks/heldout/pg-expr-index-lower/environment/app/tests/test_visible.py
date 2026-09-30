from library.api import identify_member
from library.models import Member
from library.repositories.members import active_names


def test_existing_lookup_and_export(db):
    Member.objects.create(id=1,branch_id=7,email='Reader@Example.ORG',display_name='Alex',active=True)
    Member.objects.create(id=2,branch_id=7,email='reader@example.org',display_name='Closed',active=False)
    Member.objects.create(id=3,branch_id=8,email='reader@example.org',display_name='Other',active=True)
    assert identify_member(7,'READER@example.org') == {'matches':[{'id':1,'email':'Reader@Example.ORG','display_name':'Alex'}]}
    assert active_names(7) == ['Alex']


def test_absent_member(db):
    assert identify_member(7,'absent@example.org') == {'matches':[]}
