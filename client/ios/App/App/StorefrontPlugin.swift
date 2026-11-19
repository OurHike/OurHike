import Capacitor
import StoreKit

/// Which App Store storefront this install buys through (#1876).
///
/// Apple's guidelines key the rule on purchase links to the storefront, not
/// to where the hiker stands: "In all other storefronts, except for the
/// United States storefront, where this prohibition does not apply, apps
/// and their metadata may not include buttons, external links, or other
/// calls to action that direct customers to purchasing mechanisms other
/// than in-app purchase" (App Review Guidelines 3.1.1(a), read 2026-10-27).
/// So the app offers a paid choice only when this answers the United
/// States, and lib/storefront.ts treats any other answer, or none, as not.
///
/// `Storefront.current` is StoreKit 2 (iOS 15, this target's minimum). Its
/// `countryCode` is ISO 3166-1 alpha-3 ("USA"). Compiled on every push by
/// build-shells.yml; never run by anything but a phone.
@objc(StorefrontPlugin)
public class StorefrontPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "StorefrontPlugin"
    public let jsName = "Storefront"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "getCountry", returnType: CAPPluginReturnPromise)
    ]

    @objc func getCountry(_ call: CAPPluginCall) {
        Task {
            if let code = await Storefront.current?.countryCode {
                call.resolve(["country": code])
            } else {
                // No storefront (signed out of the App Store): no answer,
                // which the app reads as "not the United States".
                call.resolve([:])
            }
        }
    }
}

/// Capacitor's bridge view controller with OurHike's own plugins added. A
/// plugin that lives in the app rather than in a package is registered here
/// (Capacitor's "Custom Native iOS Code" guide).
class OurHikeBridgeViewController: CAPBridgeViewController {
    override open func capacitorDidLoad() {
        bridge?.registerPluginInstance(StorefrontPlugin())
    }
}
