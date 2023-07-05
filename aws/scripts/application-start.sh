source ~/.bashrc
cd /dz-bot/bot 
npm install typescript
npm install
npm run commands:register > /dev/null 2> /dev/null < /dev/null &
npm start > /dev/null 2> /dev/null < /dev/null &