sudo - travis
rvm install 2.3.0
rvm use 2.3.0
cd builds
# Install travis-build to generate a .sh out of .travis.yml
cd builds
git clone https://github.com/travis-ci/travis-build.git
cd travis-build
gem install travis
travis # to create ~/.travis
ln -s `pwd` ~/.travis/travis-build
bundle install
bundle add travis
bundle binstubs travis

# Create project dir, assuming your project is `AUTHOR/PROJECT` on GitHub
cd ~/builds
mkdir rmcmaho
cd rmcmaho
git clone https://github.com/rmcmaho/scd.git
cd scd
# change to the branch or commit you want to investigate
/home/travis/.travis/travis-build/bin/travis compile > ci.sh
# Output script defaults to using branch ''
sed -i "s/\\\\'\\\\'/\\\\'master\\\\'/g" ci.sh
# You most likely will need to edit ci.sh as it ignores matrix and env
bash ci.sh
