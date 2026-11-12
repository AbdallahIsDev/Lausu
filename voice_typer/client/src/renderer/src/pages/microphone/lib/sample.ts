// Measured-skeleton sample for the Microphone page. While the device
// bundle is null the <Skeleton> measures this sample's render, so it
// needs three typical devices (a default, a USB mic, a webcam) plus
// every config field the test card and preset selector read.

import { SAMPLE_CONFIG } from "@/components/skullet/sampleConfig";
import type { LausuConfig, MicrophoneDevice } from "@/types/config";

export interface MicrophoneSampleData {
	microphones: MicrophoneDevice[];
	config: LausuConfig;
}

// Stable "<hostapi>|<name>" ids, the shape enumeration persists.
export const SAMPLE_MICROPHONES: MicrophoneDevice[] = [
	{
		index: 0,
		id: "WASAPI|Microphone Array (Realtek(R) Audio)",
		name: "Microphone Array (Realtek(R) Audio)",
		host_api: "WASAPI",
		default: true,
		channels: 2,
		rate: 48000,
	},
	{
		index: 1,
		id: "WASAPI|Razer Seiren X",
		name: "Razer Seiren X",
		host_api: "WASAPI",
		channels: 2,
		rate: 48000,
	},
	{
		index: 2,
		id: "WASAPI|Logitech Webcam C920",
		name: "Logitech Webcam C920",
		host_api: "WASAPI",
		channels: 1,
		rate: 44100,
	},
];

// System Default selected (microphone: null) with the Auto preset.
export const MICROPHONE_SAMPLE: MicrophoneSampleData = {
	microphones: SAMPLE_MICROPHONES,
	config: {
		...SAMPLE_CONFIG,
		microphone: null,
		audio_preset: "auto",
		noise_suppression_method: "none",
	},
};
