package org.ourhike.app;

import com.android.billingclient.api.BillingClient;
import com.android.billingclient.api.BillingClientStateListener;
import com.android.billingclient.api.BillingResult;
import com.android.billingclient.api.GetBillingConfigParams;
import com.android.billingclient.api.PendingPurchasesParams;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Which Google Play country this install buys through (#1876).
 *
 * Google's US rules let an app link to its own payment page for "users in
 * the United States" (Play Console Help, "An update regarding Google Play's
 * policies for developers serving users in the US", read 2026-10-27), and
 * Play Billing's BillingConfig is how an app learns the country of the
 * user's Play account. The app offers a paid choice only when this answers
 * "US"; lib/storefront.ts reads any other answer, or none, as not.
 *
 * Nothing is bought through Play Billing: the client is opened, asked one
 * question, and closed. Compiled on every push by build-shells.yml; never
 * run by anything but a phone.
 */
@CapacitorPlugin(name = "Storefront")
public class StorefrontPlugin extends Plugin {

    @PluginMethod
    public void getCountry(PluginCall call) {
        AtomicBoolean answered = new AtomicBoolean(false);
        BillingClient client = BillingClient.newBuilder(getContext())
            .setListener((result, purchases) -> {})
            .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
            .build();
        client.startConnection(
            new BillingClientStateListener() {
                @Override
                public void onBillingSetupFinished(BillingResult setup) {
                    if (setup.getResponseCode() != BillingClient.BillingResponseCode.OK) {
                        answer(call, client, answered, null);
                        return;
                    }
                    client.getBillingConfigAsync(
                        GetBillingConfigParams.newBuilder().build(),
                        (result, config) -> {
                            boolean ok = result.getResponseCode() == BillingClient.BillingResponseCode.OK && config != null;
                            answer(call, client, answered, ok ? config.getCountryCode() : null);
                        }
                    );
                }

                @Override
                public void onBillingServiceDisconnected() {
                    answer(call, client, answered, null);
                }
            }
        );
    }

    /** Resolve once, with the country or with nothing, and close the client. */
    private static void answer(PluginCall call, BillingClient client, AtomicBoolean answered, String country) {
        if (!answered.compareAndSet(false, true)) return;
        JSObject out = new JSObject();
        if (country != null) out.put("country", country);
        call.resolve(out);
        client.endConnection();
    }
}
