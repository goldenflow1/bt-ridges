from library.repositories.members import email_lookup


def find_cards(branch_id, email):
    return list(email_lookup(branch_id,email).values('id','email','display_name'))
