plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Release signing: CI decodes QUESTS_RELEASE_KEYSTORE_B64 to this path and
// supplies the passwords as env vars (see .github/workflows/android.yml).
// Locally unset → release builds fall back to unsigned (fine for manual
// `assembleRelease` testing; installDebug/adb still use the debug key).
val releaseKeystorePath = System.getenv("QUESTS_RELEASE_KEYSTORE_PATH")
val releaseKeystorePassword = System.getenv("QUESTS_RELEASE_KEYSTORE_PASSWORD")
val releaseKeyAlias = System.getenv("QUESTS_RELEASE_KEY_ALIAS")
val releaseKeyPassword = System.getenv("QUESTS_RELEASE_KEY_PASSWORD")
val hasReleaseSigning = !releaseKeystorePath.isNullOrBlank()

// versionCode must strictly increase between installed updates — CI passes
// -PqcVersionCode=<run number> so nobody has to remember to bump it by hand.
// versionName stays a manually-maintained human string below.
val ciVersionCode = (project.findProperty("qcVersionCode") as String?)?.toIntOrNull()

android {
    namespace = "com.quests.hud"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.quests.hud"
        minSdk = 26
        targetSdk = 34
        versionCode = ciVersionCode ?: 1
        versionName = "0.1"
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                storeFile = file(releaseKeystorePath!!)
                storePassword = releaseKeystorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        debug {
            // Side-by-side with the CI release APK: same phone can keep
            // com.quests.hud (release, versionCode from CI) and install
            // com.quests.hud.debug without VERSION_DOWNGRADE / signature clash.
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = false
            if (hasReleaseSigning) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-ktx:1.9.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.fragment:fragment-ktx:1.8.2")
    implementation("androidx.viewpager2:viewpager2:1.1.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
