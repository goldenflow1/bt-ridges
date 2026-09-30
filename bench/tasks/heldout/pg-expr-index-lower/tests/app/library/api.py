from library.services.access import find_cards


def identify_member(branch_id, email):
    if not isinstance(email,str):
        raise TypeError('email must be text')
    return {'matches':find_cards(branch_id,email)}
