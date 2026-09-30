from library.models import Member


def email_lookup(branch_id, email):
    return (Member.objects.annotate(normalized_email=Member.email_expression())
            .filter(branch_id=branch_id, active=True, normalized_email=email.lower()).order_by('id'))


def active_names(branch_id):
    return list(Member.objects.filter(branch_id=branch_id,active=True).order_by('display_name','id')
                .values_list('display_name',flat=True))
