# Project Rules

- AI document workflows must prioritize strong OCR/image understanding for Chinese warehouse documents, especially delivery notes that generate inbound drafts.
- AI may create and inspect drafts, but submit/audit/complete/void/delete actions must stay manual unless the user explicitly authorizes a high-risk operation.
- WeChat text or screenshot shipment notices such as "明天发鑫达 6204轴承 100套，M8螺母 500个" are supplier delivery notices and must generate inbound delivery/purchase receipt drafts, not purchase requests.
- AI must never modify, reset, or set any user account password (including the admin bootstrap password) unless the user explicitly authorizes the specific operation. Password operations require explicit prior approval.
