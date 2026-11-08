"""Public, secret-free Android shell for the UAPC NM production web controller."""
from pathlib import Path
root=Path("generated-controller")
java=root/"app/src/main/java/my/nm/uapc"
java.mkdir(parents=True,exist_ok=True)
(root/"settings.gradle").write_text("""pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement { repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); repositories { google(); mavenCentral() } }
rootProject.name='UAPC-NM-Controller'
include ':app'
""")
(root/"build.gradle").write_text("plugins { id 'com.android.application' version '8.7.3' apply false }\n")
(root/"gradle.properties").write_text("org.gradle.jvmargs=-Xmx1536m\nandroid.useAndroidX=true\n")
(root/"app/build.gradle").write_text("""plugins { id 'com.android.application' }
android {
 namespace 'my.nm.uapc'
 compileSdk 35
 defaultConfig { applicationId 'my.nm.uapc'; minSdk 26; targetSdk 35; versionCode 1; versionName '0.1.0' }
}
""")
(root/"app/src/main/AndroidManifest.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
<uses-permission android:name="android.permission.INTERNET"/>
<application android:label="UAPC NM" android:usesCleartextTraffic="false" android:theme="@android:style/Theme.Material.Light.NoActionBar">
<activity android:name=".MainActivity" android:exported="true">
<intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter>
</activity></application></manifest>
""")
(java/"MainActivity.java").write_text("""package my.nm.uapc;
import android.app.Activity;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebChromeClient;
import android.content.Intent;
import android.net.Uri;
public class MainActivity extends Activity {
 private WebView web;
 private static final String HOST="uapc-android-development.vercel.app";
 @Override public void onCreate(Bundle state) {
  super.onCreate(state);
  web=new WebView(this);
  web.getSettings().setJavaScriptEnabled(true);
  web.getSettings().setDomStorageEnabled(true);
  CookieManager.getInstance().setAcceptCookie(true);
  web.setWebChromeClient(new WebChromeClient());
  web.setWebViewClient(new WebViewClient() {
   @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest req) {
    Uri uri=req.getUrl();
    if ("https".equals(uri.getScheme()) && HOST.equals(uri.getHost())) return false;
    if ("https".equals(uri.getScheme())) startActivity(new Intent(Intent.ACTION_VIEW,uri));
    return true;
   }
  });
  setContentView(web);
  web.loadUrl("https://"+HOST+"/");
 }
 @Override public void onBackPressed() {
  if(web.canGoBack()) web.goBack(); else super.onBackPressed();
 }
 @Override protected void onPause() { CookieManager.getInstance().flush(); super.onPause(); }
}
""")
print("UAPC NM public controller shell generated")
