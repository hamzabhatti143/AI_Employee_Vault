import base64, logging, sys, time
from email.mime.text import MIMEText
from gmail_watcher import get_service

logger = logging.getLogger(__name__)


def send_email(to, subject, body):
    """Compose and send a new email."""
    service = get_service()
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(
        userId='me', body={'raw': raw}
    ).execute()
    logger.info(f'Email sent to {to}, id={result["id"]}')
    return result


def reply_to_email(message_id, body):
    """Reply in-thread to an existing email."""
    service = get_service()

    # Fetch original message for threading headers
    original = service.users().messages().get(
        userId='me', id=message_id, format='metadata',
        metadataHeaders=['Subject', 'From', 'Message-ID', 'References'],
    ).execute()

    headers = {h['name']: h['value'] for h in original.get('payload', {}).get('headers', [])}
    thread_id = original.get('threadId')
    orig_subject = headers.get('Subject', '')
    orig_from = headers.get('From', '')
    orig_msg_id = headers.get('Message-ID', '')
    references = headers.get('References', '')

    # Build reply
    reply = MIMEText(body)
    reply['to'] = orig_from
    reply['subject'] = f'Re: {orig_subject}' if not orig_subject.startswith('Re:') else orig_subject
    reply['In-Reply-To'] = orig_msg_id
    reply['References'] = f'{references} {orig_msg_id}'.strip()

    raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
    result = service.users().messages().send(
        userId='me', body={'raw': raw, 'threadId': thread_id}
    ).execute()
    logger.info(f'Reply sent to {orig_from}, thread={thread_id}')
    return result


def send_bulk_email(recipients, subject, body, delay=2):
    """Send the same email to multiple recipients with a delay between each.

    Args:
        recipients: List of email addresses.
        subject: Email subject line.
        body: Email body text.
        delay: Seconds to wait between sends (default 2) to avoid rate limits.

    Returns:
        Dict with 'sent', 'failed' lists and 'total' count.
    """
    sent = []
    failed = []
    for i, to in enumerate(recipients):
        to = to.strip()
        if not to:
            continue
        try:
            send_email(to, subject, body)
            sent.append(to)
            logger.info(f'Bulk email {i+1}/{len(recipients)} sent to {to}')
        except Exception as e:
            failed.append({"email": to, "error": str(e)})
            logger.error(f'Bulk email failed for {to}: {e}')
        if i < len(recipients) - 1:
            time.sleep(delay)
    return {"sent": sent, "failed": failed, "total": len(sent) + len(failed)}


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print('Usage:')
        print('  python gmail_utils.py reply <message_id> "reply text"')
        print('  python gmail_utils.py send "to@email.com" "subject" "body"')
        print('  python gmail_utils.py bulk "email1,email2,..." "subject" "body"')
        sys.exit(1)

    action = sys.argv[1]
    if action == 'reply' and len(sys.argv) == 4:
        reply_to_email(sys.argv[2], sys.argv[3])
        print('Reply sent!')
    elif action == 'send' and len(sys.argv) == 5:
        send_email(sys.argv[2], sys.argv[3], sys.argv[4])
        print('Email sent!')
    elif action == 'bulk' and len(sys.argv) == 5:
        recipients = [e.strip() for e in sys.argv[2].split(',') if e.strip()]
        print(f'Sending to {len(recipients)} recipients...')
        result = send_bulk_email(recipients, sys.argv[3], sys.argv[4])
        print(f'Done: {len(result["sent"])} sent, {len(result["failed"])} failed')
        if result['failed']:
            for f in result['failed']:
                print(f'  FAILED: {f["email"]} — {f["error"]}')
    else:
        print('Invalid arguments.')
        print('  python gmail_utils.py reply <message_id> "reply text"')
        print('  python gmail_utils.py send "to@email.com" "subject" "body"')
        print('  python gmail_utils.py bulk "email1,email2,..." "subject" "body"')
        sys.exit(1)
