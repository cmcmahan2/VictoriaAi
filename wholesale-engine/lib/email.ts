export type AlertEmailPayload = {
  to: string;
  market: string;
  hotDeals: number;
  topDeal?: { address: string; score: number; profit: number };
};

export async function sendAlertEmail(payload: AlertEmailPayload): Promise<void> {
  const apiKey = process.env.RESEND_API_KEY;

  if (!apiKey) {
    console.log('[email] RESEND_API_KEY not set — alert email skipped:', payload);
    return;
  }

  const body = {
    from: 'Wholesale Engine <alerts@yourdomain.com>',
    to: payload.to,
    subject: `${payload.hotDeals} new wholesale deals in ${payload.market}`,
    html: `
      <h2>New Wholesale Deals Found</h2>
      <p><strong>Market:</strong> ${payload.market}</p>
      <p><strong>Hot Deals (75+):</strong> ${payload.hotDeals}</p>
      ${payload.topDeal ? `
        <h3>Top Deal</h3>
        <p>${payload.topDeal.address}</p>
        <p>Score: ${payload.topDeal.score} | Est. Profit: $${payload.topDeal.profit.toLocaleString()}</p>
      ` : ''}
      <p><a href="http://localhost:3002/search">View all deals →</a></p>
    `,
  };

  try {
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.text();
      console.error('[email] Resend error:', err);
    }
  } catch (err) {
    console.error('[email] Failed to send alert email:', err);
  }
}
