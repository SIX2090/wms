# Project Rules

- AI document workflows must prioritize strong OCR/image understanding for Chinese warehouse documents, especially delivery notes that generate inbound drafts.
- AI may create and inspect drafts, but submit/audit/complete/void/delete actions must stay manual unless the user explicitly authorizes a high-risk operation.
- WeChat text or screenshot shipment notices such as "明天发鑫达 6204轴承 100套，M8螺母 500个" are supplier delivery notices and must generate inbound delivery/purchase receipt drafts, not purchase requests.
- AI must never modify, reset, or set any user account password (including the admin bootstrap password) unless the user explicitly authorizes the specific operation. Password operations require explicit prior approval.
- After completing any task, AI must verify the result (e.g., check service status, test functionality, confirm output correctness) before reporting to the user. Unverified results must not be presented as done.
- After completing any task, AI must commit and push changes to GitHub unless the user explicitly says not to.
