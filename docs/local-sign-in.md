# Local Tesla sign-in

Version 0.1.1 adds a test path for signing in with your regular Tesla account. The integration and the session run in your Home Assistant. The browser opens Tesla's own sign-in page. The tracker does not ask for your Tesla password or a developer application.

1. Add **Tesla Order Tracker** under **Settings → Devices & services → Add integration**.
2. Choose **Sign in with Tesla (paste callback address)**. Open the Tesla link from the form on a desktop computer and keep the Home Assistant tab open.
3. In the Tesla tab, open the browser's developer tools, then select **Network** and enable **Preserve log** before signing in. If the browser asks to open the Tesla app after sign-in, dismiss that prompt.
4. Copy the full `tesla://auth/callback` address from the console or the `Location` field of the final network redirect. Paste it directly into the masked field in Home Assistant and submit. Do not share the address or export the browser network log.

The address is tied to that setup attempt and expires. An updated Tesla link on the form starts a new attempt. If more than one order is returned, choose the order after signing in.

This test reads the order list. Some order details from the separate NAS implementation are not available in this build. The local workflow relies on a Tesla sign-in path that may change. See [README](../README.md) for data storage information.
