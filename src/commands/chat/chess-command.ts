/* eslint-disable import/no-extraneous-dependencies */
import axios from 'axios';
import { ChatInputCommandInteraction, PermissionsString } from 'discord.js';
import { RateLimiter } from 'discord.js-rate-limiter';

import { Language } from '../../models/enum-helpers/index.js';
import { EventData } from '../../models/internal-models.js';
import { Lang } from '../../services/index.js';
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

    public async execute(intr: ChatInputCommandInteraction, data: EventData): Promise<void> {
        await InteractionUtils.send(intr, Lang.getEmbed('displayEmbeds.chess', data.lang));

        const headers = {
            Authorization: 'Bearer ' + this.lichessToken,
        };

        const res = await axios.post('https://lichess.org/api/challenge/open', { headers });

        await InteractionUtils.send(intr, res.data.challenge.url);
    }
}
