from googletrans import Translator

class MessageTranslator():
    def __init__(self):
        self.__translator = Translator()
        
    def chat_auto_translate(self, message):
        fixed_message, emotes = self.__strip_message_for_translate(message)
        detected = self.__translator.detect(fixed_message)
        if detected.lang != 'en' and detected.confidence > 0.95:
            translated = self.__translator.translate(fixed_message)
            fixed_message = self.__fix_stripped_message(translated.text, emotes)
            return translated.src, translated.dest, fixed_message
            
        return None, None, None
        
    def __strip_message_for_translate(self, message):
        if not 'emotes' in message.tags or message.tags['emotes'] == '':
            return message.content, []
            
        emotes = message.tags['emotes'].split('/')
        to_replace = []
        for emote in emotes:
            id, replacement = emote.split(':')
            splices = replacement.split(',')
            for splice in splices:
                start, end = splice.split('-')
                to_replace.append((int(start), int(end)+1, id))
        
        to_replace = sorted(to_replace, key=lambda x: x[0], reverse=True)
        
        emote_text = {}
        new_message = message.content
        for start, end, id in to_replace:
            if not id in emote_text:
                emote_text[id] = new_message[start:end]
            new_message = f'{new_message[:start]}__{id}__{new_message[end:]}'
            
        return new_message, emote_text
        
    def __fix_stripped_message(self, message, emotes):
        for emote_id in emotes:
            message = message.replace(f'__{emote_id}__', emotes[emote_id])
            
        return message