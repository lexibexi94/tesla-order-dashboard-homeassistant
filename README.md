# Tesla Order Tracker for Home Assistant

A community integration that adds a Tesla order page to the Home Assistant sidebar. Version 0.1.0 is a test build. The demo is ready to try. Live tracking through Tesla Fleet is experimental.

## Try it in Home Assistant 2026.11 or newer

1. [Open Tesla Order Tracker in your Home Assistant Marketplace](https://my.home-assistant.io/redirect/marketplace_repository/?owner=lexibexi94&repository=tesla-order-dashboard-homeassistant&category=integration). This first install adds a custom repository. Home Assistant will ask you to connect GitHub if you have not already done so.
2. Select **Install** and follow the prompt. If setup does not open automatically, go to **Settings → Devices & services → Add integration → Tesla Order Tracker**.
3. Choose **Try the demo**. Open **Tesla Order Tracker** in the sidebar and select **Simulate change**. The two example changes show a revised delivery window and an appointment.
4. To test push, open the integration's **Configure** options and select a phone already connected through the Home Assistant Companion App. Demo messages are labeled and are off until you select a phone.

If the button does not open the repository, use **Settings → Marketplace → Add from link** with this repository's URL and select **Integration**. The Marketplace installs the current default branch while this project is in early testing.

## Connect a real order (experimental)

This option requires your own Tesla Developer application registered for your region. Start with the [Tesla Fleet API onboarding guide](https://developer.tesla.com/docs/fleet-api/getting-started/what-is-fleet-api) and [Home Assistant's Tesla Fleet application setup](https://www.home-assistant.io/integrations/tesla_fleet/#setting-up-the-developer-application). Set the allowed redirect URI to `https://my.home-assistant.io/redirect/oauth` if using the default My Home Assistant integration. In Home Assistant, add your Client ID and Client Secret as **Application credentials** for **Tesla Order Tracker**. Then add the integration, choose **Connect Tesla Fleet**, select your region, and sign in on Tesla's site. If more than one active order is returned, select the order to track. This reader does not send any vehicle commands or require vehicle key pairing for its own order requests. Tesla may require developer app registration and apply charges under its API terms.

The reader checks the documented [active-orders endpoint](https://developer.tesla.com/docs/fleet-api/endpoints/user-endpoints) every 30 minutes. An experimental manual refresh is limited to one read per minute and honors Tesla's rate limits. It displays only fields returned by that endpoint. A VIN, delivery window, appointment, or production status can be missing. A limited response cannot be used to determine what happened to an order when it disappears, so the dashboard retains the last known values and shows the problem. Live OAuth and field coverage still need confirmation against an active order.

## Local data

Home Assistant stores the OAuth credentials and the selected order internally. Keep backups private. The tracker stores the last known fields and up to 40 changes locally, keeps order references out of entity states and notifications, and omits VINs from the timeline and pushes. The VIN, if available, is a Home Assistant sensor and may be retained by Recorder under its normal settings. Removing an integration entry deletes its tracker snapshot and timeline. Recorder and backups follow their own retention settings. The sidebar panel is visible to administrators.

The demo and each live order have separate state. This repository contains only source code and synthetic values. It is a community project and has no affiliation with Tesla or Home Assistant.

[Deutsch: Kurzanleitung](docs/install-de.md)
