"""Public, standalone four-template Android source generator.

There is no network access to any private UAPC repository or Neon database.
Only deterministic, allowlisted native Android applications are generated.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re

TEMPLATES = {
    "tasks": (r"\b(?:tugas(?:an)?|todo|to-do|tasks?|checklist)\b", "Tugasan"),
    "notes": (r"\b(?:nota|catatan|notes?|memo)\b", "Catatan"),
    "inventory": (r"\b(?:inventori|inventory|stok|stock|barang)\b", "Inventori"),
    "expenses": (r"\b(?:belanja|perbelanjaan|expenses?|budget|bajet|kewangan)\b", "Belanja"),
}
# Extensible registry for independently reviewed application families.
# Modules must be explicitly registered; never fetch or execute user-supplied code.
try:
    from builder.registry import register_templates, resolve_template
except ModuleNotFoundError:
    from registry import register_templates, resolve_template
register_templates(TEMPLATES)
MAX_OBJECTIVE = 180

ACTIVITY = r'''package %PACKAGE%;

import android.app.Activity;
import android.os.Bundle;
import android.content.Context;
import android.content.SharedPreferences;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.Locale;

public final class MainActivity extends Activity {
    private final String kind = "%KIND%";
    private JSONArray entries = new JSONArray();
    private LinearLayout rows;
    private EditText nameField;
    private EditText detailsField;
    private TextView summary;

    private void persist() {
        SharedPreferences prefs = getPreferences(Context.MODE_PRIVATE);
        prefs.edit().putString("records", entries.toString()).apply();
    }
    private void restore() {
        try {
            String json = getPreferences(Context.MODE_PRIVATE).getString("records", "[]");
            entries = new JSONArray(json);
        } catch (Exception exception) {
            entries = new JSONArray();
        }
    }
    private void removeAt(int position) {
        JSONArray kept = new JSONArray();
        for (int i = 0; i < entries.length(); i++) {
            if (i != position) kept.put(entries.opt(i));
        }
        entries = kept;
        persist();
        render();
    }
    private TextView text(String value, int size) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setPadding(5, 8, 5, 8);
        return view;
    }
    private void render() {
        rows.removeAllViews();
        double total = 0;
        for (int i = 0; i < entries.length(); i++) {
            final int index = i;
            JSONObject item = entries.optJSONObject(i);
            if (item == null) continue;
            LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setPadding(10, 10, 10, 10);
            if (kind.equals("tasks")) {
                CheckBox completed = new CheckBox(this);
                completed.setText(item.optString("name", ""));
                completed.setChecked(item.optBoolean("done", false));
                completed.setOnCheckedChangeListener((v, checked) -> {
                    JSONObject current = entries.optJSONObject(index);
                    if (current != null) {
                        try { current.put("done", checked); persist(); }
                        catch (Exception ignored) {}
                    }
                });
                card.addView(completed);
            } else {
                card.addView(text(item.optString("name", ""), 18));
                card.addView(text(item.optString("detail", ""), 14));
                if (kind.equals("expenses")) {
                    try { total += Double.parseDouble(item.optString("detail", "0")); }
                    catch (NumberFormatException ignored) {}
                }
            }
            Button delete = new Button(this);
            delete.setText("Padam rekod");
            delete.setOnClickListener(v -> removeAt(index));
            card.addView(delete);
            rows.addView(card);
        }
        if (kind.equals("expenses")) {
            summary.setText(String.format(Locale.US, "Jumlah: RM %.2f", total));
        } else {
            summary.setText("Bilangan rekod: " + entries.length());
        }
    }
    private void addRecord() {
        String name = nameField.getText().toString().trim();
        if (name.isEmpty() || name.length() > 120) {
            Toast.makeText(this, "Isi nama rekod (maksimum 120 aksara)", Toast.LENGTH_SHORT).show();
            return;
        }
        String detail = detailsField == null ? "" : detailsField.getText().toString().trim();
        if (detail.length() > 4000) {
            Toast.makeText(this, "Butiran terlalu panjang", Toast.LENGTH_SHORT).show();
            return;
        }
        if (kind.equals("expenses")) {
            try {
                double amount = Double.parseDouble(detail);
                if (!Double.isFinite(amount) || amount < 0 || amount > 100000000)
                    throw new NumberFormatException();
            } catch (NumberFormatException exception) {
                Toast.makeText(this, "Masukkan jumlah RM yang sah", Toast.LENGTH_SHORT).show();
                return;
            }
        }
        try {
            JSONObject item = new JSONObject();
            item.put("name", name);
            item.put("detail", detail);
            item.put("done", false);
            entries.put(item);
            persist();
            nameField.setText("");
            if (detailsField != null) detailsField.setText("");
            render();
        } catch (Exception exception) {
            Toast.makeText(this, "Rekod tidak dapat disimpan", Toast.LENGTH_SHORT).show();
        }
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        restore();
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(22, 24, 22, 16);

        root.addView(text(getString(R.string.app_name), 25));
        root.addView(text("Aplikasi luar talian • Nyamuk Menggigit", 13));

        nameField = new EditText(this);
        nameField.setSingleLine(true);
        nameField.setHint("Nama rekod");
        root.addView(nameField);

        if (!kind.equals("tasks")) {
            detailsField = new EditText(this);
            if (kind.equals("notes")) {
                detailsField.setHint("Isi nota");
                detailsField.setMinLines(3);
                detailsField.setInputType(InputType.TYPE_CLASS_TEXT |
                    InputType.TYPE_TEXT_FLAG_MULTI_LINE);
            } else if (kind.equals("inventory")) {
                detailsField.setHint("Kuantiti atau keterangan stok");
            } else {
                detailsField.setHint("Amaun (RM)");
                detailsField.setInputType(InputType.TYPE_CLASS_NUMBER |
                    InputType.TYPE_NUMBER_FLAG_DECIMAL);
            }
            root.addView(detailsField);
        }
        Button add = new Button(this);
        add.setText("Tambah");
        add.setOnClickListener(v -> addRecord());
        root.addView(add);

        summary = text("", 15);
        root.addView(summary);

        ScrollView scroll = new ScrollView(this);
        rows = new LinearLayout(this);
        rows.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(rows);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        render();
    }
}
'''

def classify(objective: str) -> str:
    if not isinstance(objective, str) or not (1 <= len(objective.strip()) <= MAX_OBJECTIVE):
        raise ValueError("Arahan perlu antara 1 dan 180 aksara")
    # This is a four-template builder, NOT a general application generator.
    # Reject unsupported requirements before matching incidental words such as
    # "tugasan" in a complex PhoneCare / worker / automation specification.
    unsupported = (
        r"phone[ -]?care|penyelenggaraan|imbas(?:an)?|scan(?:ning)?|"
        r"pendua|duplicate|duplikat|bersih(?:kan)?|cleanup|"
        r"worker|heartbeat|automasi|automation|"
        r"fail sampah|storage cleaner|storan"
    )
    kind = resolve_template(objective)
    if kind in TEMPLATES and re.search(unsupported, objective, re.IGNORECASE):
        raise ValueError("Objektif memerlukan fungsi yang tidak disokong pembina templat; APK tidak dibina")
    return kind


def generate(objective: str, title: str, destination: Path) -> dict:
    kind = classify(objective)
    # Registry entries describe possible families, but only reviewed generators
    # can produce an APK. Never silently compile a generic app for a new family.
    if kind not in TEMPLATES:
        raise ValueError('Modul aplikasi belum mempunyai penjana Android yang disahkan')
    if not isinstance(title, str):
        raise ValueError("Nama aplikasi mesti teks")
    title = title.strip() or "NM " + TEMPLATES[kind][1]
    if not (1 <= len(title) <= 48) or any(ord(c) < 32 for c in title):
        raise ValueError("Nama aplikasi tidak sah")
    suffix = hashlib.sha256((kind + ":" + title).encode()).hexdigest()[:10]
    package = "my.nm.publicbuilder." + kind + ".a" + suffix
    files = {
        "settings.gradle": (
            "pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }\n"
            "dependencyResolutionManagement { repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); "
            "repositories { google(); mavenCentral() } }\n"
            "rootProject.name = 'UAPCNMPublicBuilder'\ninclude ':app'\n"
        ),
        "build.gradle": "plugins { id 'com.android.application' version '8.7.3' apply false }\n",
        "gradle.properties": "org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8\nandroid.useAndroidX=true\n",
        "app/build.gradle": (
            "plugins { id 'com.android.application' }\n"
            "android {\n"
            "  namespace '" + package + "'\n"
            "  compileSdk 35\n"
            "  defaultConfig {\n"
            "    applicationId '" + package + "'\n"
            "    minSdk 24\n"
            "    targetSdk 35\n"
            "    versionCode 1\n"
            "    versionName '1.0.0'\n"
            "  }\n"
            "}\n"
        ),
        "app/src/main/AndroidManifest.xml": (
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android">'
            '<application android:label="@string/app_name" android:allowBackup="false" '
            'android:theme="@android:style/Theme.Material.Light.NoActionBar">'
            '<activity android:name=".MainActivity" android:exported="true">'
            '<intent-filter><action android:name="android.intent.action.MAIN"/>'
            '<category android:name="android.intent.category.LAUNCHER"/>'
            '</intent-filter></activity></application></manifest>\n'
        ),
        "app/src/main/res/values/strings.xml": (
            '<resources><string name="app_name">' + html.escape(title, quote=True).replace("'", "\\'") +
            '</string></resources>\n'
        ),
        "app/src/main/java/" + package.replace(".", "/") + "/MainActivity.java": (
            ACTIVITY.replace("%PACKAGE%", package).replace("%KIND%", kind)
        ),
    }
    destination = Path(destination)
    for relative_path, content in files.items():
        path = destination / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return {"template": kind, "title": title, "package": package,
            "files": len(files), "apk_built": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Public Android APK template generator")
    parser.add_argument("--objective", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--out", default="generated")
    args = parser.parse_args()
    metadata = generate(args.objective, args.title, Path(args.out))
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
