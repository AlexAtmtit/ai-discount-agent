# Multi-Platform Considerations (Bonus A)

This document outlines the platform-specific considerations for integrating with Instagram, TikTok, and WhatsApp APIs. While the core business logic remains consistent across platforms, there are key differences in APIs, messaging constraints, and compliance requirements.

## Platform Comparison

### Instagram (Meta Graph API v18+)

#### Webhook Implementation
- **Endpoint**: `POST /webhook/instagram`
- **Signature Verification**: HMAC-SHA256 with app secret
- **Field Mapping**:
  - `id` → `message_id`
  - `from.id` → `user_id`
  - `message.text` → `raw_incoming_message`
- **Rate Limits**: 200 calls/minute, 10k tokens/hour per access token
- **Reply Window**: 24 hours for active conversations, no limit for 7 days

#### Content Restrictions
- No character limit for text messages
- Media support: images, videos, stories, reels
- Business account required for API access
- Messenger plugin for web DMs

#### Compliance
- GDPR compliant for EU users
- Content moderation required for user-generated content
- 24-hour customer customer support window requirement

---

### TikTok (TikTok for Developers API)

#### Webhook Implementation
- **Endpoint**: `POST /webhook/tiktok`
- **Signature Verification**: SHA256 with app secret + timestamp
- **Field Mapping**:
  - `conversation_id` → `thread_id`
  - `sender.id` → `user_id`
  - `message.text` → `raw_incoming_message`
  - `message_id` → `message_id`
- **Rate Limits**: 5000 requests/hour per app
- **Reply Window**: 24 hours for direct messages

#### Content Restrictions
- 4000 character limit per message
- Rich media support with TikTok-specific content
- Business account verification required
- TikTok profile links can be included in responses

#### Compliance
- Child safety policies strict enforcement
- Anti-spam measures for promotional content
- Country-specific content regulations

---

### WhatsApp Business API (360 Dialog/Meta)

#### Webhook Implementation
- **Endpoint**: `POST /webhook/whatsapp`
- **Signature Verification**: X-Hub-Signature-256 header validation
- **Field Mapping**:
  - `contacts[0].wa_id` → `user_id`
  - `messages[0].id` → `message_id`
  - `messages[0].text.body` → `raw_incoming_message`
- **Rate Limits**: 1000 messages/day free tier, paid tiers up to 250k
- **Reply Window**: 24 hours for session continuity

#### Content Restrictions
- 4096 character limit per message
- Rich text with formatting (*bold*, _italic_, ~strikethrough~)
- Media support with size limits (images: 5MB, videos: 16MB)
- Template messages for initial contact required after 24h window

#### Compliance
- Sender verification through business verification
- Opt-in consent required for marketing messages
- End-to-end encryption (messages stored encrypted)
- Regulatory compliance for different countries

## Unified Normalizer

Our `normalizer.py` handles platform differences by:

```python
def normalize_message(raw_payload: dict) -> IncomingMessage:
    """Normalize platform-specific payload to internal format"""
    platform = get_platform_from_webhook(raw_payload)

    # Extract common fields based on platform
    if platform == "instagram":
        message = raw_payload["entry"][0]["messaging"][0]["message"]
        user_id = message["sender"]["id"]
        text = message.get("text", "")
    elif platform == "tiktok":
        message = raw_payload["messages"][0]
        user_id = message["sender"]["id"]
        text = message.get("text", "")
    elif platform == "whatsapp":
        message = raw_payload["messages"][0]
        user_id = message["from"]
        text = message.get("body", "")

    return IncomingMessage(
        platform=platform,
        user_id=user_id,
        text=text.lower().strip(),
        # other fields...
    )
```

## Platform-Specific Challenges

### Instagram Challenges
- Complex nested webhook payload structure
- Messenger API requires app review for production
- Media-rich messages need special handling

### TikTok Challenges
- Relatively new API with frequent changes
- Business account verification process
- Country-specific API availability

### WhatsApp Challenges
- Phone number verification required
- Template message requirements for unsolicited contact
- High cost compared to organic channels

## Implementation Strategy

1. **Abstract Platform Interface**: Define a common interface for platform API interactions
2. **Circuit Breaker Pattern**: Handle temporary API outages gracefully
3. **Queue-Based Processing**: Use Redis/queue for webhook reliability
4. **Platform-Specific Tests**: Separate test suites for each platform's unik constraints

## Testing Considerations

- Mock platform APIs in unit tests
- Use test phone numbers/sendboxes for integration tests
- Validate webhook signatures in test environment
- Test 24-hour reply windows with simulated timestamps

## Production Deployment Notes

- Use webhooks with signature verification enabled
- Implement webhook retry mechanisms
- Monitor API rate limits per platform
- Set up platform-specific alerting for failures
- Regular updates for API changes
