package org.ourhike.app;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // OurHike's own plugins, before the bridge starts (Capacitor's
        // "Custom Native Android Code" guide).
        registerPlugin(StorefrontPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
