// Outreach email sending via Resend.
// https://resend.com/docs/api-reference/emails/send-email

export type OutreachEmail = {
  to: string;
  domain: string;
  askPrice: number;
  senderName: string;
  senderEmail: string; // must be a verified domain in Resend
  buyerProfile?: string; // e.g. "AI dev-tool startups"
};

export type SendResult =
  | { ok: true; id: string }
  | { ok: false; error: string };

function buildEmailHtml(email: OutreachEmail): string {
  const { domain, askPrice, senderName, buyerProfile } = email;
  const formattedPrice = '$' + askPrice.toLocaleString();
  return `
<!DOCTYPE html>
<html>
<body style="font-family: Georgia, serif; font-size: 15px; color: #222; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px;">
  <p>Hi,</p>
  <p>
    I wanted to reach out because I own <strong>${domain}</strong> and thought it might be
    a strong fit for your brand${buyerProfile ? ` — especially given the space you're in (${buyerProfile})` : ''}.
  </p>
  <p>
    The domain is short, memorable, and directly relevant to what you do. I'm offering it for
    <strong>${formattedPrice}</strong>, which includes a clean transfer.
  </p>
  <p>
    If you're interested or have any questions, just reply to this email and I'd be happy to
    chat. If the timing isn't right, no worries at all.
  </p>
  <p>Best,<br/>${senderName}</p>
  <hr style="border: none; border-top: 1px solid #eee; margin-top: 30px;"/>
  <p style="font-size: 12px; color: #999;">
    You received this email because ${domain} is potentially relevant to your business.
    If you'd prefer not to receive emails like this, just reply with "unsubscribe."
  </p>
</body>
</html>`.trim();
}

function buildEmailText(email: OutreachEmail): string {
  const { domain, askPrice, senderName, buyerProfile } = email;
  const formattedPrice = '$' + askPrice.toLocaleString();
  return [
    `Hi,`,
    ``,
    `I wanted to reach out because I own ${domain} and thought it might be a strong fit for your brand${buyerProfile ? ` — especially given the space you're in (${buyerProfile})` : ''}.`,
    ``,
    `The domain is short, memorable, and directly relevant to what you do. I'm offering it for ${formattedPrice}, which includes a clean transfer.`,
    ``,
    `If you're interested or have any questions, just reply to this email and I'd be happy to chat. If the timing isn't right, no worries at all.`,
    ``,
    `Best,`,
    senderName,
    ``,
    `---`,
    `You received this email because ${domain} is potentially relevant to your business. If you'd prefer not to receive emails like this, reply with "unsubscribe."`,
  ].join('\n');
}

export async function sendOutreachEmail(
  email: OutreachEmail,
  apiKey: string,
): Promise<SendResult> {
  const { domain, to, senderName, senderEmail } = email;
  const subject = `${domain} — available for acquisition`;

  try {
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: `${senderName} <${senderEmail}>`,
        to: [to],
        subject,
        html: buildEmailHtml(email),
        text: buildEmailText(email),
      }),
      signal: AbortSignal.timeout(10000),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { message?: string };
      return { ok: false, error: body.message ?? `Resend returned HTTP ${res.status}` };
    }

    const data = (await res.json()) as { id: string };
    return { ok: true, id: data.id };
  } catch (e) {
    return { ok: false, error: `Network error: ${(e as Error).message}` };
  }
}
