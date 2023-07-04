/* eslint-disable import/no-extraneous-dependencies */
import { ChatInputCommandInteraction, PermissionsString } from 'discord.js';
import { RateLimiter } from 'discord.js-rate-limiter';

import { Language } from '../../models/enum-helpers/index.js';
import { HttpService, Lang, Logger } from '../../services/index.js';
import { InteractionUtils } from '../../utils/index.js';
import { Command, CommandDeferType } from '../index.js';

export class ChessCommand implements Command {
    public names = [Lang.getRef('chatCommands.chess', Language.Default)];
    public cooldown = new RateLimiter(1, 5000);
    public deferType = CommandDeferType.PUBLIC;
    public requireClientPerms: PermissionsString[] = [];
    private lichessToken: string;

    constructor(lichessToken: string) {
        this.lichessToken = lichessToken;
    }

    public async execute(intr: ChatInputCommandInteraction): Promise<void> {
        const httpService = new HttpService();
        const auth = 'Bearer ' + this.lichessToken;

        Logger.info('Fetching chess data for new match', {});
        const response = await httpService.post('https://lichess.org/api/challenge/open', auth, {});
        const resData: any = await response.json();
        resData && Logger.info('Chess URL fetched, sending it in channel', {});

        await InteractionUtils.send(intr, resData.challenge.url);
        Logger.info('Message sent', {});
    }
}
