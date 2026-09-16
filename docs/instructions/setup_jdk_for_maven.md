setting the project's Java version won't fix this, because it's already set to 21 in three places (pom.xml's <java.version>, .java-version, .sdkmanrc). None of those control which JVM runs mvn itself — they only tell the compiler what bytecode to target. The Java 25 problem is entirely about which JDK launches Maven's own process, before it ever reads your pom.

So the fix has to happen outside the project's Java-version declarations. Three real options, scoped to not touching anything global unless you choose to:

1. direnv + .envrc (recommended — ledger-only, zero shell-profile edits)


brew install direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc   # one-time, needed for direnv itself to activate
Then a single .envrc file inside services/fintracker-ledger/:


export JAVA_HOME=/usr/local/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
direnv allow once, and from then on JAVA_HOME is set to 21 automatically only while your shell is inside that folder — nothing else on the machine is affected, and it can be committed to the repo so it works for anyone who clones it and has direnv.

2. jenv (the standard per-project Java-version tool)


brew install jenv
echo 'export PATH="$HOME/.jenv/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(jenv init -)"' >> ~/.zshrc
jenv add /usr/local/Cellar/openjdk@21/21.0.6
It then reads the .java-version file already sitting in the repo (21) and auto-switches per-directory. More setup steps, but it's built exactly for this and needs no new file since .java-version already exists.

3. Global JAVA_HOME in ~/.zshrc — simplest, one line, but affects every project on this machine, not just the ledger:


export JAVA_HOME=$(/usr/libexec/java_home -v 21)
All three point at the JDK 21 already installed via brew (openjdk@21 — no download needed).