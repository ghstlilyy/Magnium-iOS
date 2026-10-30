import Foundation

// A native Magnium feature with a switch in Settings ▸ Magnium.
public enum MagniumFeature: String, CaseIterable {
    // Appearance
    case hideEditedLabel
    case timeWithSeconds
    case fullDateInMessages
    case showMessageId
    case magniumTitle
    case deletedMarkerIcon
    case hidePremiumRow
    case hideStarsRow
    case hideBusinessRow
    case hideHelpSection
    case hideGiftRow
    case hideChatListStatuses
    case hideContactsTab
    // Features
    case keepScreenAwakeInChats
    case disableSwipeToReply
    case silentByDefault
    case stripTrackingParameters
    case confirmCalls
    // Just for fun
    case romanTime
    case binaryTime
    case backwardsTime
    case emojiClock
    case hexTime

    public enum Category: String, CaseIterable {
        case appearance
        case features
        case fun

        public var title: String {
            switch self {
            case .appearance:
                return "Внешний вид"
            case .features:
                return "Функции"
            case .fun:
                return "По приколу"
            }
        }
    }

    public var category: Category {
        switch self {
        case .hideEditedLabel, .timeWithSeconds, .fullDateInMessages, .showMessageId, .magniumTitle, .deletedMarkerIcon, .hidePremiumRow, .hideStarsRow, .hideBusinessRow, .hideHelpSection, .hideGiftRow, .hideChatListStatuses, .hideContactsTab:
            return .appearance
        case .keepScreenAwakeInChats, .disableSwipeToReply, .silentByDefault, .stripTrackingParameters, .confirmCalls:
            return .features
        case .romanTime, .binaryTime, .backwardsTime, .emojiClock, .hexTime:
            return .fun
        }
    }

    public var title: String {
        switch self {
        case .hideEditedLabel:
            return "Скрывать «изменено»"
        case .timeWithSeconds:
            return "Секунды во времени сообщений"
        case .fullDateInMessages:
            return "Дата у каждого сообщения"
        case .showMessageId:
            return "Номер сообщения у времени"
        case .magniumTitle:
            return "«Magnium» вместо «Чаты»"
        case .deletedMarkerIcon:
            return "🗑 вместо слова «удалено»"
        case .hidePremiumRow:
            return "Скрыть Telegram Premium"
        case .hideStarsRow:
            return "Скрыть Звёзды"
        case .hideBusinessRow:
            return "Скрыть Telegram для бизнеса"
        case .hideHelpSection:
            return "Скрыть раздел помощи"
        case .hideGiftRow:
            return "Скрыть «Отправить подарок»"
        case .hideChatListStatuses:
            return "Без статусов в списке чатов"
        case .hideContactsTab:
            return "Скрыть вкладку «Контакты»"
        case .keepScreenAwakeInChats:
            return "Не гасить экран в чатах"
        case .disableSwipeToReply:
            return "Без свайпа для ответа"
        case .silentByDefault:
            return "Отправлять без звука"
        case .stripTrackingParameters:
            return "Убирать слежку из ссылок"
        case .confirmCalls:
            return "Подтверждать звонки"
        case .romanTime:
            return "Время римскими цифрами"
        case .binaryTime:
            return "Время в двоичном коде"
        case .backwardsTime:
            return "Время задом наперёд"
        case .emojiClock:
            return "Часы-эмодзи у времени"
        case .hexTime:
            return "Время в шестнадцатеричном"
        }
    }

    public var subtitle: String? {
        switch self {
        case .showMessageId:
            return "Например «#1234 12:30»"
        case .deletedMarkerIcon:
            return "Для плагина «Антиудаление»"
        case .hidePremiumRow, .hideStarsRow, .hideBusinessRow, .hideHelpSection, .hideGiftRow:
            return "В главном меню настроек"
        case .keepScreenAwakeInChats:
            return "Пока открыт чат, экран не гаснет"
        case .disableSwipeToReply:
            return "Ответ — через меню сообщения"
        case .silentByDefault:
            return "Получатели не услышат уведомления"
        case .stripTrackingParameters:
            return "utm_, fbclid, si и подобное — при отправке"
        case .confirmCalls:
            return "Чтобы не позвонить случайно"
        case .romanTime:
            return "XII:XXX вместо 12:30"
        case .binaryTime:
            return "1100:11110 вместо 12:30"
        case .backwardsTime:
            return "03:21 вместо 12:30"
        case .emojiClock:
            return "🕧 12:30"
        case .hideChatListStatuses:
            return "Эмодзи-статусы и звёзды Premium у имён"
        case .hideContactsTab:
            return "Контакты останутся в кнопке нового сообщения"
        case .hexTime:
            return "C:1E вместо 12:30"
        case .magniumTitle:
            return "В заголовке и на вкладке"
        default:
            return nil
        }
    }

    public var defaultValue: Bool {
        return false
    }
}

public extension Notification.Name {
    static let magniumSettingsChanged = Notification.Name("MagniumSettingsChanged")
}

public enum MagniumSettings {
    private static let prefix = "magnium.feature."

    public static func isOn(_ feature: MagniumFeature) -> Bool {
        let defaults = UserDefaults.standard
        let key = self.prefix + feature.rawValue
        if defaults.object(forKey: key) == nil {
            return feature.defaultValue
        }
        return defaults.bool(forKey: key)
    }

    public static func set(_ feature: MagniumFeature, isOn: Bool) {
        UserDefaults.standard.set(isOn, forKey: self.prefix + feature.rawValue)
        NotificationCenter.default.post(name: .magniumSettingsChanged, object: nil, userInfo: ["feature": feature.rawValue])
    }

    public static func features(in category: MagniumFeature.Category) -> [MagniumFeature] {
        return MagniumFeature.allCases.filter { $0.category == category }
    }
}

// The message time styles of the fun features.
public enum MagniumTimeStyle {
    public static func romanNumeral(_ value: Int) -> String {
        if value == 0 {
            return "N"
        }
        let table: [(Int, String)] = [(50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
        var remaining = value
        var result = ""
        for (number, numeral) in table {
            while remaining >= number {
                result += numeral
                remaining -= number
            }
        }
        return result
    }

    // The clock face nearest to the time: 🕛 ... 🕧.
    public static func clockEmoji(hours: Int, minutes: Int) -> String {
        let hourFaces = ["🕛", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚"]
        let halfFaces = ["🕧", "🕜", "🕝", "🕞", "🕟", "🕠", "🕡", "🕢", "🕣", "🕤", "🕥", "🕦"]
        var hour = hours % 12
        var half = false
        if minutes >= 45 {
            hour = (hour + 1) % 12
        } else if minutes >= 15 {
            half = true
        }
        return half ? halfFaces[hour] : hourFaces[hour]
    }

    // "12:30" -> "12:30:07" (also inside longer text such as "30 Oct at 12:30 PM").
    public static func addingSeconds(to text: String, timestamp: Int32) -> String {
        let characters = Array(text)
        var index = 0
        while index + 2 < characters.count {
            if characters[index].isNumber, characters[index + 1] == ":", characters[index + 2].isNumber, index + 3 < characters.count, characters[index + 3].isNumber {
                let insertAt = index + 4
                let seconds = String(format: ":%02d", Int(timestamp % 60))
                return String(characters[0 ..< insertAt]) + seconds + String(characters[insertAt...])
            }
            index += 1
        }
        return text
    }

    // Applies the enabled fun styles to a "12:30" style time; other text is left as is.
    public static func apply(to text: String) -> String {
        var result = text
        let parts = text.split(separator: ":")
        if parts.count >= 2, let hours = Int(parts[0].suffix(2)), let minutes = Int(parts[1].prefix(2)) {
            let prefix = String(parts[0].dropLast(min(2, parts[0].count)))
            let suffix = String(parts[1].dropFirst(min(2, parts[1].count)))
            if MagniumSettings.isOn(.romanTime) {
                result = "\(prefix)\(self.romanNumeral(hours)):\(self.romanNumeral(minutes))\(suffix)"
            } else if MagniumSettings.isOn(.binaryTime) {
                result = "\(prefix)\(String(hours, radix: 2)):\(String(minutes, radix: 2))\(suffix)"
            } else if MagniumSettings.isOn(.hexTime) {
                result = "\(prefix)\(String(format: "%X", hours)):\(String(format: "%02X", minutes))\(suffix)"
            }
            if MagniumSettings.isOn(.emojiClock) {
                result = "\(self.clockEmoji(hours: hours, minutes: minutes)) \(result)"
            }
        }
        if MagniumSettings.isOn(.backwardsTime) {
            result = String(result.reversed())
        }
        return result
    }
}
